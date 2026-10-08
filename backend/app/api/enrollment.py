"""Device enrollment API routes."""

import secrets
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Device, DeviceIdentity, User, EnrollmentToken, AuditEvent
from app.schemas import (
    CreateEnrollmentRequest,
    CreateEnrollmentResponse,
    EnrollDeviceRequest,
    EnrollDeviceResponse,
    EnrollmentStatusResponse,
)
from app.security import get_current_user
from app.crypto.ed25519 import verify_enrollment_proof
import uuid

router = APIRouter(prefix="/api/v1/enrollment", tags=["Enrollment"])


@router.post("/create", response_model=CreateEnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    request: CreateEnrollmentRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create an enrollment token for a device."""
    # Generate cryptographically secure token
    token = secrets.token_hex(32)  # 64 hex chars
    device_id = secrets.token_hex(16)  # 32 hex chars
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Store enrollment token
    enrollment = EnrollmentToken(
        id=uuid.uuid4(),
        token=token,
        device_id=device_id,
        user_id=current_user.id,
        device_name=request.device_name,
        used=False,
        cancelled=False,
        expires_at=expires_at,
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    db.add(enrollment)
    
    # Audit log
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="enrollment_created",
        actor_id=current_user.id,
        actor_type="user",
        action="create_enrollment",
        result="success",
        details={"device_id": device_id, "device_name": request.device_name},
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.add(audit_event)
    await db.commit()
    
    return CreateEnrollmentResponse(
        enrollment_token=token,
        device_id=device_id,
        expires_at=expires_at,
    )


@router.post("/enroll", response_model=EnrollDeviceResponse, status_code=status.HTTP_201_CREATED)
async def enroll_device(
    request: EnrollDeviceRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Enroll a device using an enrollment token."""
    # Look up enrollment token
    result = await db.execute(
        select(EnrollmentToken).where(EnrollmentToken.token == request.enrollment_token)
    )
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ENROLLMENT_FAILED", "message": "Invalid enrollment token"}
        )
    
    # Check if token is used
    if enrollment.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ENROLLMENT_FAILED", "message": "Enrollment token already used"}
        )
    
    # Check if token is cancelled
    if enrollment.cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ENROLLMENT_FAILED", "message": "Enrollment token was cancelled"}
        )
    
    # Check expiration
    if datetime.utcnow() > enrollment.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ENROLLMENT_FAILED", "message": "Enrollment token expired"}
        )
    
    # Check device ID binding
    if enrollment.device_id != request.device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ENROLLMENT_FAILED", "message": "Device ID mismatch"}
        )
    
    # Verify Ed25519 signature
    signature_valid = verify_enrollment_proof(
        request.device_id,
        request.timestamp,
        request.signature,
        request.public_key
    )
    
    if not signature_valid:
        # Audit log failed enrollment
        audit_event = AuditEvent(
            id=uuid.uuid4(),
            event_type="enrollment_failed",
            actor_type="device",
            action="enroll",
            result="failure",
            details={
                "device_id": request.device_id,
                "reason": "invalid_signature",
            },
            ip_address=http_request.client.host if http_request.client else None,
        )
        db.add(audit_event)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ENROLLMENT_FAILED", "message": "Invalid cryptographic signature"}
        )
    
    # Check if device already exists
    result = await db.execute(
        select(Device).where(Device.device_id == request.device_id)
    )
    existing_device = result.scalar_one_or_none()
    
    if existing_device:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "ENROLLMENT_FAILED", "message": "Device already registered"}
        )
    
    # Create device
    device = Device(
        id=uuid.uuid4(),
        device_id=request.device_id,
        owner_id=enrollment.user_id,
        name=enrollment.device_name,
        public_key=request.public_key,
        os_type=request.os_type,
        os_version=request.os_version or "",
        agent_version=request.agent_version or "0.1.0",
        status="pending",
        approved=False,
    )
    
    db.add(device)
    await db.flush()
    
    # Create device identity
    identity = DeviceIdentity(
        id=uuid.uuid4(),
        device_id=device.id,
        public_key=request.public_key,
        key_type="ed25519",
        active=True,
    )
    db.add(identity)
    
    # Mark enrollment token as used
    enrollment.used = True
    enrollment.used_at = datetime.utcnow()
    
    # Audit log
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="device_enrolled",
        actor_id=device.id,
        actor_type="device",
        target_type="device",
        target_id=device.id,
        action="enroll",
        result="success",
        details={
            "device_id": request.device_id,
            "os_type": request.os_type,
            "agent_version": request.agent_version,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.add(audit_event)
    await db.commit()
    
    return EnrollDeviceResponse(
        device_id=device.id,
        device_identity=request.device_id,
        status="pending",
        message="Device enrolled successfully. Awaiting owner approval.",
    )


@router.get("/status/{token}", response_model=EnrollmentStatusResponse)
async def get_enrollment_status(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Check enrollment token status."""
    result = await db.execute(
        select(EnrollmentToken).where(EnrollmentToken.token == token)
    )
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND"}
        )
    
    is_expired = datetime.utcnow() > enrollment.expires_at
    
    return EnrollmentStatusResponse(
        valid=not enrollment.used and not enrollment.cancelled and not is_expired,
        used=enrollment.used,
        cancelled=enrollment.cancelled,
        expired=is_expired,
        expires_at=enrollment.expires_at,
    )


@router.post("/cancel/{token}", response_model=dict)
async def cancel_enrollment(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an enrollment token."""
    result = await db.execute(
        select(EnrollmentToken).where(
            EnrollmentToken.token == token,
            EnrollmentToken.user_id == current_user.id
        )
    )
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND"}
        )
    
    enrollment.cancelled = True
    
    # Audit log
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="enrollment_cancelled",
        actor_id=current_user.id,
        actor_type="user",
        action="cancel_enrollment",
        result="success",
        details={"token": token[:8] + "..."},
    )
    db.add(audit_event)
    await db.commit()
    
    return {"cancelled": True}

"""Device management API routes."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import Device, User, AuditEvent
from app.schemas import DeviceRegister, DeviceResponse, DeviceListResponse
from app.security import get_current_user, require_role
from app.websocket import manager
import uuid

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])


@router.get("/", response_model=DeviceListResponse)
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all devices for the authenticated user."""
    result = await db.execute(
        select(Device).where(Device.owner_id == current_user.id)
    )
    devices = result.scalars().all()
    
    return DeviceListResponse(
        devices=[DeviceResponse.model_validate(d) for d in devices],
        total=len(devices)
    )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get device details."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    return DeviceResponse.model_validate(device)


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    request: DeviceRegister,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a new device."""
    # Generate device identity
    device_identity = uuid.uuid4().hex
    
    # Create device
    device = Device(
        id=uuid.uuid4(),
        device_id=device_identity,
        owner_id=current_user.id,
        name=request.name,
        public_key=request.public_key,
        os_type=request.os_type,
        os_version=request.os_version or "",
        agent_version=request.agent_version or "0.1.0",
        status="offline",
        approved=False,
    )
    
    db.add(device)
    await db.flush()
    
    # Audit log
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="device_registered",
        actor_id=current_user.id,
        actor_type="user",
        target_type="device",
        target_id=device.id,
        action="register",
        result="success",
        details={"device_id": device_identity, "name": request.name},
    )
    db.add(audit_event)
    await db.commit()
    
    return DeviceResponse.model_validate(device)


@router.patch("/{device_id}/approve", response_model=dict)
async def approve_device(
    device_id: str,
    current_user: User = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Approve a device."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    device.approved = True
    device.updated_at = datetime.utcnow()
    
    # Audit log
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="device_approved",
        actor_id=current_user.id,
        actor_type="user",
        target_type="device",
        target_id=device.id,
        action="approve",
        result="success",
    )
    db.add(audit_event)
    await db.commit()
    
    return {"id": str(device.id), "approved": True}


@router.patch("/{device_id}/revoke", response_model=dict)
async def revoke_device(
    device_id: str,
    current_user: User = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Revoke a device."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    device.approved = False
    device.status = "revoked"
    device.updated_at = datetime.utcnow()
    
    # Audit log
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="device_revoked",
        actor_id=current_user.id,
        actor_type="user",
        target_type="device",
        target_id=device.id,
        action="revoke",
        result="success",
    )
    db.add(audit_event)
    await db.commit()

    # Immediately terminate any currently authenticated local WebSocket sessions.
    # Future connections are rejected by the WebSocket authentication path.
    await manager.close_device_connections(device.device_id, reason="Device revoked")

    return {"id": str(device.id), "revoked": True}


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a device."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    # Terminate any active local connection before removing the device.
    await manager.close_device_connections(device.device_id, reason="Device deleted")

    # Audit log before deletion
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="device_deleted",
        actor_id=current_user.id,
        actor_type="user",
        target_type="device",
        target_id=device.id,
        action="delete",
        result="success",
    )
    db.add(audit_event)
    
    await db.delete(device)
    await db.commit()
    
    return None

"""Session management API routes."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models import ConnectionSession, Device, User, AuditEvent
from app.schemas import StartSessionRequest, SessionResponse, SessionListResponse
from app.security import get_current_user
import uuid

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's sessions."""
    result = await db.execute(
        select(ConnectionSession)
        .where(ConnectionSession.user_id == current_user.id)
        .order_by(desc(ConnectionSession.started_at))
        .limit(50)
    )
    sessions = result.scalars().all()
    
    # Get device names
    session_responses = []
    for session in sessions:
        device_result = await db.execute(
            select(Device).where(Device.id == session.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        session_responses.append(SessionResponse(
            id=session.id,
            type=session.type,
            status=session.status,
            started_at=session.started_at,
            ended_at=session.ended_at,
            duration=session.duration,
            device_id=session.device_id,
            device_name=device.name if device else None,
        ))
    
    return SessionListResponse(
        sessions=session_responses,
        total=len(session_responses)
    )


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    request: StartSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a new session."""
    # Verify device ownership and approval
    result = await db.execute(
        select(Device).where(
            Device.id == str(request.device_id),
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    if not device.approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "DEVICE_NOT_APPROVED"}
        )
    
    if device.status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "DEVICE_REVOKED"}
        )
    
    # Create session
    session = ConnectionSession(
        id=uuid.uuid4(),
        user_id=current_user.id,
        device_id=request.device_id,
        type=request.type,
        status="active",
    )
    
    db.add(session)
    
    # Audit
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="session_started",
        actor_id=current_user.id,
        actor_type="user",
        target_type="session",
        target_id=session.id,
        action="start_session",
        result="success",
        details={"type": request.type, "device_id": str(request.device_id)},
    )
    db.add(audit_event)
    await db.commit()
    
    return SessionResponse(
        id=session.id,
        type=session.type,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration=session.duration,
        device_id=session.device_id,
        device_name=device.name,
    )


@router.post("/{session_id}/end", response_model=dict)
async def end_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End a session."""
    result = await db.execute(
        select(ConnectionSession).where(
            ConnectionSession.id == session_id,
            ConnectionSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SESSION_NOT_FOUND"}
        )
    
    ended_at = datetime.utcnow()
    duration = int((ended_at - session.started_at).total_seconds())
    
    session.status = "ended"
    session.ended_at = ended_at
    session.duration = duration
    
    # Audit
    audit_event = AuditEvent(
        id=uuid.uuid4(),
        event_type="session_ended",
        actor_id=current_user.id,
        actor_type="user",
        target_type="session",
        target_id=session_id,
        action="end_session",
        result="success",
        details={"duration": duration},
    )
    db.add(audit_event)
    await db.commit()
    
    return {"id": session_id, "status": "ended", "duration": duration}

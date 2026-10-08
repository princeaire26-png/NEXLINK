"""Remote-control session API backed by PostgreSQL and the NEXLINK WebSocket fabric."""
from __future__ import annotations
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Device, User, AuditEvent, ConnectionSession
from app.schemas import CreateRemoteSessionRequest, RemoteSessionResponse
from app.security import get_current_user
from app.platform.permissions import authorize

router = APIRouter(prefix="/api/v1/remote", tags=["Remote Access"])


def now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/sessions", response_model=RemoteSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_remote_session(request: CreateRemoteSessionRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    decision = authorize(current_user.role, "remote:control", "remote.control", explicit_approval=True)
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    device = (await db.execute(select(Device).where(Device.id == request.device_id, Device.owner_id == current_user.id))).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail={"error": "DEVICE_NOT_FOUND"})
    if not device.approved:
        raise HTTPException(status_code=403, detail={"error": "DEVICE_NOT_APPROVED"})
    if device.status == "revoked":
        raise HTTPException(status_code=403, detail={"error": "DEVICE_REVOKED"})
    if device.status != "online":
        raise HTTPException(status_code=409, detail={"error": "DEVICE_OFFLINE"})
    existing = (await db.execute(select(ConnectionSession).where(ConnectionSession.device_id == device.id, ConnectionSession.user_id == current_user.id, ConnectionSession.type == "remote_desktop", ConnectionSession.status.in_(["active", "connecting"])))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail={"error": "SESSION_ALREADY_ACTIVE", "session_id": str(existing.id)})
    session = ConnectionSession(id=uuid.uuid4(), user_id=current_user.id, device_id=device.id, type="remote_desktop", status="active", metadata_={"transport": "direct-first-relay-fallback", "quality": "adaptive"})
    db.add(session)
    db.add(AuditEvent(id=uuid.uuid4(), event_type="remote_session_created", actor_id=current_user.id, actor_type="user", target_type="device", target_id=device.id, action="create_remote_session", result="success", details={"session_id": str(session.id)}))
    await db.commit()
    return RemoteSessionResponse(session_id=session.id, device_id=device.id, state="connecting")


@router.get("/sessions")
async def list_remote_sessions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConnectionSession, Device.name).join(Device, Device.id == ConnectionSession.device_id).where(ConnectionSession.user_id == current_user.id).order_by(desc(ConnectionSession.started_at)).limit(100))
    sessions = [{"id": str(s.id), "device_id": str(s.device_id), "device_name": name, "state": s.status, "created_at": s.started_at.isoformat(), "ended_at": s.ended_at.isoformat() if s.ended_at else None, "metadata": s.metadata_} for s, name in result.all()]
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_remote_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConnectionSession).where(ConnectionSession.id == session_id, ConnectionSession.user_id == current_user.id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND"})
    return {"id": str(session.id), "device_id": str(session.device_id), "state": session.status, "created_at": session.started_at.isoformat(), "ended_at": session.ended_at.isoformat() if session.ended_at else None, "metadata": session.metadata_}


@router.delete("/sessions/{session_id}")
async def terminate_remote_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConnectionSession).where(ConnectionSession.id == session_id, ConnectionSession.user_id == current_user.id, ConnectionSession.status.in_(["active", "connecting"])))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND"})
    session.status = "ended"; session.ended_at = now()
    session.duration = max(0, int((session.ended_at - session.started_at).total_seconds()))
    db.add(AuditEvent(id=uuid.uuid4(), event_type="remote_session_terminated", actor_id=current_user.id, actor_type="user", target_type="session", target_id=session.id, action="terminate_remote_session", result="success", details={"device_id": str(session.device_id)}))
    await db.commit()
    return {"id": str(session.id), "state": "ended"}

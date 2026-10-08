"""NEXLINK network-guard control API."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditEvent, Device, User
from app.schemas import NetworkGuardRequest
from app.security import get_current_user
from app.platform.permissions import authorize
from app.websocket import manager

router = APIRouter(prefix="/api/v1/devices", tags=["Network Guard"])

ACTION_MAP = {
    "block_all": "network.block_all",
    "unblock_all": "network.unblock_all",
    "block_domains": "network.block_domains",
    "status": "network.status",
}

@router.post("/{device_id}/network-guard", response_model=dict)
async def network_guard(
    device_id: str,
    request: NetworkGuardRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Device).where(Device.id == device_id, Device.owner_id == current_user.id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "DEVICE_NOT_FOUND"})
    decision = authorize(current_user.role, "network:manage", "network.domain_policy" if request.action == "block_domains" else "network.block" if request.action == "block_all" else "network.unblock", explicit_approval=True)
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    if not device.approved or device.status == "revoked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "DEVICE_NOT_APPROVED"})
    if request.action == "block_domains" and not request.domains:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": "DOMAINS_REQUIRED"})

    request_id = str(uuid.uuid4())
    action = ACTION_MAP[request.action]
    params = {"domains": request.domains} if request.action == "block_domains" else {}
    delivered = await manager.send_action(device.device_id, request_id, action, params)
    if not delivered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "DEVICE_OFFLINE"})

    db.add(AuditEvent(
        id=uuid.uuid4(), event_type="network_guard_action", actor_id=current_user.id,
        actor_type="user", target_type="device", target_id=device.id,
        action=action, result="delivered", details={"request_id": request_id, **params},
    ))
    await db.commit()
    return {"request_id": request_id, "action": request.action, "delivered": True}

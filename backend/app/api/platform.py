"""NEXLINK Command Center APIs: fleet, RMM, AI governance, automation and security."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    User, Device, DeviceGroup, DeviceGroupMember, DeviceAlert, DeviceSoftware,
    AccessPolicy, AIActionRequest, Automation, AutomationRun, AuditEvent, Membership,
    SupportRequest, RelayNode,
)
from app.security import get_current_user, require_role
from app.platform.ai import make_plan, authorize_tool
from app.platform.automation import matches_trigger, validate_actions
from app.platform.permissions import authorize
from app.websocket import manager

router = APIRouter(prefix="/api/v1/platform", tags=["NEXLINK Platform"])


def now() -> datetime:
    return datetime.now(timezone.utc)


async def user_org(db: AsyncSession, user: User):
    result = await db.execute(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at).limit(1))
    membership = result.scalar_one_or_none()
    return membership.organization_id if membership else None


async def owned_device(db: AsyncSession, user: User, device_id: uuid.UUID) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id, Device.owner_id == user.id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail={"error": "DEVICE_NOT_FOUND"})
    return device


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    rules: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True


class AutomationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    trigger_config: dict[str, Any]
    actions: list[dict[str, Any]]
    enabled: bool = True


class AIPlanRequest(BaseModel):
    device_id: uuid.UUID
    intent: str = Field(min_length=3, max_length=2000)


class AIAuthorizeRequest(BaseModel):
    approved: bool


class SupportCreate(BaseModel):
    device_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


@router.get("/summary")
async def platform_summary(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    devices = await db.execute(select(Device).where(Device.owner_id == current_user.id))
    rows = devices.scalars().all()
    alerts = await db.execute(select(func.count(DeviceAlert.id)).join(Device).where(Device.owner_id == current_user.id, DeviceAlert.state == "open"))
    sessions = await db.execute(select(func.count()).select_from(AIActionRequest).where(AIActionRequest.user_id == current_user.id, AIActionRequest.status == "pending"))
    return {
        "product": "NEXLINK",
        "motto": "Connect. Control. Understand. Automate.",
        "devices": {"total": len(rows), "online": sum(d.status == "online" for d in rows), "offline": sum(d.status == "offline" for d in rows), "pending": sum(not d.approved for d in rows), "revoked": sum(d.status == "revoked" for d in rows)},
        "open_alerts": int(alerts.scalar() or 0),
        "pending_ai_actions": int(sessions.scalar() or 0),
        "capabilities": ["remote_access", "device_management", "network_guard", "ai", "security_center", "automation", "multi_tenant", "offline_lan"],
    }


@router.get("/devices/{device_id}/inventory")
async def device_inventory(device_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    device = await owned_device(db, current_user, device_id)
    software = await db.execute(select(DeviceSoftware).where(DeviceSoftware.device_id == device.id).order_by(DeviceSoftware.name))
    return {"device": {"id": str(device.id), "name": device.name, "os": device.os_type, "os_version": device.os_version, "agent_version": device.agent_version}, "inventory": {**(device.metadata_ or {}), "software": [{"id": str(s.id), "name": s.name, "version": s.version, "publisher": s.publisher, "install_date": s.install_date, "source": s.source, "metadata": s.metadata_} for s in software.scalars().all()]}}


@router.get("/devices/{device_id}/alerts")
async def device_alerts(device_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    device = await owned_device(db, current_user, device_id)
    result = await db.execute(select(DeviceAlert).where(DeviceAlert.device_id == device.id).order_by(desc(DeviceAlert.created_at)).limit(100))
    return {"alerts": [{"id": str(a.id), "severity": a.severity, "category": a.category, "title": a.title, "message": a.message, "state": a.state, "details": a.details, "created_at": a.created_at.isoformat()} for a in result.scalars().all()]}


@router.post("/devices/{device_id}/alerts/{alert_id}/ack")
async def acknowledge_alert(device_id: uuid.UUID, alert_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    device = await owned_device(db, current_user, device_id)
    result = await db.execute(select(DeviceAlert).where(DeviceAlert.id == alert_id, DeviceAlert.device_id == device.id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="ALERT_NOT_FOUND")
    alert.state = "acknowledged"
    alert.acknowledged_at = now()
    db.add(AuditEvent(id=uuid.uuid4(), event_type="alert_acknowledged", actor_id=current_user.id, actor_type="user", target_type="device_alert", target_id=alert.id, action="acknowledge", result="success"))
    await db.commit()
    return {"id": str(alert.id), "state": alert.state}


@router.get("/groups")
async def list_groups(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    if not org_id:
        return {"groups": []}
    result = await db.execute(select(DeviceGroup).where(DeviceGroup.organization_id == org_id).order_by(DeviceGroup.name))
    groups = result.scalars().all()
    output = []
    for group in groups:
        members = await db.execute(select(DeviceGroupMember.device_id).where(DeviceGroupMember.group_id == group.id))
        output.append({"id": str(group.id), "name": group.name, "description": group.description, "device_ids": [str(x) for x in members.scalars().all()]})
    return {"groups": output}


@router.post("/groups", status_code=201)
async def create_group(request: GroupCreate, current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    if not org_id:
        raise HTTPException(status_code=400, detail="USER_HAS_NO_ORGANIZATION")
    group = DeviceGroup(id=uuid.uuid4(), organization_id=org_id, name=request.name, description=request.description)
    db.add(group)
    await db.commit()
    return {"id": str(group.id), "name": group.name, "description": group.description}


@router.post("/groups/{group_id}/devices/{device_id}")
async def add_group_device(group_id: uuid.UUID, device_id: uuid.UUID, current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    group = (await db.execute(select(DeviceGroup).where(DeviceGroup.id == group_id, DeviceGroup.organization_id == org_id))).scalar_one_or_none()
    device = await owned_device(db, current_user, device_id)
    if not group:
        raise HTTPException(status_code=404, detail="GROUP_NOT_FOUND")
    db.add(DeviceGroupMember(id=uuid.uuid4(), group_id=group.id, device_id=device.id))
    await db.commit()
    return {"group_id": str(group.id), "device_id": str(device.id)}


@router.get("/policies")
async def list_policies(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    result = await db.execute(select(AccessPolicy).where(AccessPolicy.organization_id == org_id).order_by(AccessPolicy.name))
    return {"policies": [{"id": str(p.id), "name": p.name, "enabled": p.enabled, "rules": p.rules, "capabilities": p.capabilities} for p in result.scalars().all()]}


@router.post("/policies", status_code=201)
async def create_policy(request: PolicyCreate, current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    policy = AccessPolicy(id=uuid.uuid4(), organization_id=org_id, name=request.name, rules=request.rules, capabilities=request.capabilities, enabled=request.enabled)
    db.add(policy)
    await db.commit()
    return {"id": str(policy.id), "name": policy.name, "enabled": policy.enabled}


@router.get("/automations")
async def list_automations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    result = await db.execute(select(Automation).where(Automation.organization_id == org_id).order_by(Automation.name))
    return {"automations": [{"id": str(a.id), "name": a.name, "description": a.description, "trigger": a.trigger_config, "actions": a.actions, "enabled": a.enabled, "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None} for a in result.scalars().all()]}


@router.post("/automations", status_code=201)
async def create_automation(request: AutomationCreate, current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    validate_actions(request.actions)
    org_id = await user_org(db, current_user)
    automation = Automation(id=uuid.uuid4(), organization_id=org_id, name=request.name, description=request.description, trigger_config=request.trigger_config, actions=request.actions, enabled=request.enabled)
    db.add(automation)
    await db.commit()
    return {"id": str(automation.id), "name": automation.name, "enabled": automation.enabled}


@router.post("/automations/{automation_id}/test")
async def test_automation(automation_id: uuid.UUID, event: dict[str, Any], current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    automation = (await db.execute(select(Automation).where(Automation.id == automation_id, Automation.organization_id == org_id))).scalar_one_or_none()
    if not automation:
        raise HTTPException(status_code=404, detail="AUTOMATION_NOT_FOUND")
    match = matches_trigger(automation.trigger_config, event)
    return {"matched": match.matched, "reason": match.reason, "actions": automation.actions if match.matched else []}


@router.post("/ai/plan")
async def ai_plan(request: AIPlanRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    device = await owned_device(db, current_user, request.device_id)
    plan = make_plan(request.intent)
    return {"device_id": str(device.id), "plan": plan, "security": "No action is executed merely by creating a plan. High-risk actions require explicit approval."}


@router.post("/ai/action")
async def ai_action(request: dict[str, Any], current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    device = await owned_device(db, current_user, uuid.UUID(str(request["device_id"])))
    tool_name = str(request.get("tool_name", ""))
    params = dict(request.get("parameters") or {})
    decision = authorize_tool(current_user.role, tool_name, request.get("permissions") or [], bool(request.get("approved")))
    record = AIActionRequest(id=uuid.uuid4(), organization_id=await user_org(db, current_user), user_id=current_user.id, device_id=device.id, tool_name=tool_name, parameters=params, risk_level=decision.get("risk", "unknown"), status="approved" if decision["allowed"] else "pending" if decision["requires_approval"] else "denied", decision_reason=decision["reason"])
    db.add(record)
    await db.commit()
    if decision["allowed"]:
        params["_authorized"] = True if decision.get("risk") in {"high", "critical"} else params.get("_authorized", False)
        record.parameters = params
        delivered = await manager.send_action(device.device_id, str(record.id), f"ai.{tool_name}", params)
        record.status = "dispatched" if delivered else "approved_offline"
        await db.commit()
    return {"id": str(record.id), **decision, "status": record.status}


@router.post("/ai/actions/{action_id}/authorize")
async def authorize_ai_action(action_id: uuid.UUID, request: AIAuthorizeRequest, current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIActionRequest).where(AIActionRequest.id == action_id, AIActionRequest.user_id == current_user.id))
    action = result.scalar_one_or_none()
    if not action or action.status != "pending":
        raise HTTPException(status_code=404, detail="AI_ACTION_NOT_PENDING")
    action.decided_at = now()
    if not request.approved:
        action.status = "denied"
        await db.commit()
        return {"id": str(action.id), "status": action.status}
    decision = authorize_tool(current_user.role, action.tool_name, ["ai:approve"], True)
    if not decision["allowed"]:
        action.status = "denied"
        action.decision_reason = decision["reason"]
    else:
        device = await owned_device(db, current_user, action.device_id)
        action.parameters = {**(action.parameters or {}), "_authorized": True}
        delivered = await manager.send_action(device.device_id, str(action.id), f"ai.{action.tool_name}", action.parameters)
        action.status = "dispatched" if delivered else "approved_offline"
    await db.commit()
    return {"id": str(action.id), "status": action.status, "reason": action.decision_reason}


@router.post("/support", status_code=201)
async def create_support_request(request: SupportCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if request.device_id:
        await owned_device(db, current_user, request.device_id)
    ticket = SupportRequest(id=uuid.uuid4(), organization_id=await user_org(db, current_user), requester_id=current_user.id, device_id=request.device_id, title=request.title, description=request.description, priority=request.priority)
    db.add(ticket)
    await db.commit()
    return {"id": str(ticket.id), "status": ticket.status, "priority": ticket.priority}


@router.get("/support")
async def list_support_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await user_org(db, current_user)
    result = await db.execute(select(SupportRequest).where(SupportRequest.organization_id == org_id).order_by(desc(SupportRequest.created_at)).limit(100))
    return {"requests": [{"id": str(x.id), "title": x.title, "description": x.description, "priority": x.priority, "status": x.status, "device_id": str(x.device_id) if x.device_id else None, "created_at": x.created_at.isoformat()} for x in result.scalars().all()]}


@router.get("/relay")
async def relay_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RelayNode).where(RelayNode.enabled.is_(True)).order_by(RelayNode.region))
    return {"mode": "direct-first-relay-fallback", "nodes": [{"id": str(n.id), "name": n.name, "endpoint": n.endpoint, "region": n.region, "capacity": n.capacity, "active_sessions": n.active_sessions} for n in result.scalars().all()]}


@router.post("/devices/{device_id}/maintenance")
async def device_maintenance(device_id: uuid.UUID, request: dict[str, Any], current_user: User = Depends(require_role(["owner", "admin"])), db: AsyncSession = Depends(get_db)):
    device = await owned_device(db, current_user, device_id)
    action = str(request.get("action", ""))
    mapping = {"restart":"device.restart", "shutdown":"device.shutdown", "lock":"device.lock", "restart_service":"service.restart", "terminate_process":"process.terminate", "install_software":"software.install"}
    wire_action = mapping.get(action)
    if not wire_action:
        raise HTTPException(status_code=400, detail="Unsupported maintenance action")
    decision = authorize(current_user.role, "device:manage", wire_action, explicit_approval=bool(request.get("approved")))
    if not decision.allowed:
        return {"allowed": False, "requires_approval": decision.requires_approval, "reason": decision.reason}
    params = dict(request.get("params") or {})
    params["_authorized"] = True
    delivered = await manager.send_action(device.device_id, str(uuid.uuid4()), wire_action, params)
    db.add(AuditEvent(id=uuid.uuid4(), event_type="maintenance_action", actor_id=current_user.id, actor_type="user", target_type="device", target_id=device.id, action=wire_action, result="success" if delivered else "failure", details={"delivered": delivered, "params": {k:v for k,v in params.items() if k != "_authorized"}}))
    await db.commit()
    return {"allowed": True, "delivered": delivered, "action": wire_action}

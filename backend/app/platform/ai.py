"""AI orchestration facade: plan -> policy -> approval -> execution -> verification."""
from __future__ import annotations
from dataclasses import asdict
from nexlink_ai.planner import ActionPlanner
from nexlink_ai.tools import standard_tool_definitions
from .permissions import Risk, authorize, has_capability

PLANNER = ActionPlanner()
TOOL_RISK = {tool.name: Risk[{"low": "LOW", "medium": "MEDIUM", "high": "HIGH", "critical": "CRITICAL"}[tool.risk_level.value]] for tool in standard_tool_definitions()}


def make_plan(intent: str) -> dict:
    plan = PLANNER.plan(intent)
    return {"plan_id": plan.plan_id, "intent": plan.intent, "estimated_risk": plan.estimated_risk,
            "steps": [asdict(step) for step in plan.steps]}


def authorize_tool(role: str, tool_name: str, permissions: list[str], approved: bool = False) -> dict:
    definition = next((t for t in standard_tool_definitions() if t.name == tool_name), None)
    if not definition:
        return {"allowed": False, "requires_approval": False, "reason": "Unknown AI tool"}
    risk = TOOL_RISK[tool_name]
    role_permissions = set(permissions)
    if role == "owner":
        role_permissions.update(definition.required_permissions)
    elif role == "admin":
        role_permissions.update(definition.required_permissions)
    elif role == "member" and all(p.startswith("read:") for p in definition.required_permissions):
        role_permissions.update(definition.required_permissions)
    if not all(p in role_permissions for p in definition.required_permissions):
        return {"allowed": False, "requires_approval": False, "reason": "Missing tool permission"}
    capability = "ai:approve" if definition.requires_authorization else "ai:use"
    if not has_capability(role, capability):
        return {"allowed": False, "requires_approval": False, "reason": f"Role '{role}' lacks '{capability}'"}
    operation = "security.modify" if risk == Risk.CRITICAL else "remote.terminal" if risk >= Risk.HIGH else "device.read"
    decision = authorize(role, capability, operation, explicit_approval=approved)
    return {"allowed": decision.allowed, "requires_approval": decision.requires_approval, "reason": decision.reason,
            "risk": risk.name.lower()}

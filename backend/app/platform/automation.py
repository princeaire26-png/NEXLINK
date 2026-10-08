"""Safe automation primitives for the NEXLINK event loop."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class AutomationMatch:
    matched: bool
    reason: str


def matches_trigger(trigger: dict[str, Any], event: dict[str, Any]) -> AutomationMatch:
    if trigger.get("event") and trigger["event"] != event.get("event"):
        return AutomationMatch(False, "event mismatch")
    condition = trigger.get("condition") or {}
    field = condition.get("field")
    op = condition.get("operator", "eq")
    expected = condition.get("value")
    if not field:
        return AutomationMatch(True, "event matched")
    actual = event.get(field)
    try:
        matched = {
            "eq": actual == expected,
            "gt": actual > expected,
            "gte": actual >= expected,
            "lt": actual < expected,
            "lte": actual <= expected,
            "contains": expected in actual,
        }.get(op, False)
    except TypeError:
        matched = False
    return AutomationMatch(matched, f"{field} {op} {expected!r} (actual={actual!r})")

ALLOWED_ACTIONS = {"notify", "create_alert", "request_ai_diagnosis", "request_health_check"}


def validate_actions(actions: list[dict[str, Any]]) -> None:
    for action in actions:
        name = action.get("type")
        if name not in ALLOWED_ACTIONS:
            raise ValueError(f"Automation action '{name}' is not allowed")

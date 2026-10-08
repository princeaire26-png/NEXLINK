"""Central capability and risk policy for NEXLINK operations."""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum

class Risk(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3

ROLE_CAPABILITIES: dict[str, set[str]] = {
    "owner": {"*"},
    "admin": {
        "device:read", "device:manage", "remote:view", "remote:control", "remote:file",
        "remote:terminal", "network:manage", "automation:manage", "ai:use", "ai:approve",
        "audit:read", "policy:manage", "support:manage", "inventory:read",
    },
    "member": {
        "device:read", "remote:view", "remote:control", "remote:file", "ai:use",
        "inventory:read", "support:create",
    },
    "viewer": {"device:read", "inventory:read", "audit:read", "remote:view"},
}

OPERATION_RISK: dict[str, Risk] = {
    "device.read": Risk.LOW,
    "remote.view": Risk.LOW,
    "remote.control": Risk.MEDIUM,
    "remote.file.read": Risk.MEDIUM,
    "remote.file.write": Risk.HIGH,
    "remote.terminal": Risk.HIGH,
    "network.block": Risk.HIGH,
    "network.unblock": Risk.HIGH,
    "network.domain_policy": Risk.HIGH,
    "software.install": Risk.HIGH,
    "service.restart": Risk.HIGH,
    "device.revoke": Risk.HIGH,
    "security.modify": Risk.CRITICAL,
    "device.restart": Risk.HIGH,
    "device.shutdown": Risk.HIGH,
    "device.lock": Risk.MEDIUM,
    "service.restart": Risk.HIGH,
    "process.terminate": Risk.HIGH,
    "software.install": Risk.HIGH,
}

@dataclass(frozen=True)
class Decision:
    allowed: bool
    requires_approval: bool = False
    reason: str = ""


def has_capability(role: str, capability: str) -> bool:
    caps = ROLE_CAPABILITIES.get(role, set())
    return "*" in caps or capability in caps


def authorize(role: str, capability: str, operation: str, explicit_approval: bool = False) -> Decision:
    if not has_capability(role, capability):
        return Decision(False, reason=f"Role '{role}' lacks capability '{capability}'")
    risk = OPERATION_RISK.get(operation, Risk.MEDIUM)
    if risk >= Risk.CRITICAL and not explicit_approval:
        return Decision(False, True, "Critical operation requires explicit authorization")
    if risk >= Risk.HIGH and not explicit_approval:
        return Decision(False, True, "High-risk operation requires explicit authorization")
    return Decision(True, False, "Authorized")

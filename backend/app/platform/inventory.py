"""Inventory normalization for agent-reported endpoint data."""
from __future__ import annotations
from typing import Any


def normalize_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "hardware": payload.get("hardware", {}),
        "software": payload.get("software", []),
        "network": payload.get("network", {}),
        "monitors": payload.get("monitors", []),
        "printers": payload.get("printers", []),
        "usb": payload.get("usb", []),
        "services": payload.get("services", []),
        "updated_at": payload.get("updated_at"),
    }

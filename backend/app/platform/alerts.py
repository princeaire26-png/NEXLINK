"""Deterministic RMM alert rules. Alerts are based only on real telemetry."""
from __future__ import annotations
from typing import Any


def evaluate_metrics(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    cpu = metrics.get("cpu_percent")
    memory = metrics.get("memory_percent")
    disk = metrics.get("disk_percent")
    if isinstance(cpu, (int, float)) and cpu >= 95:
        alerts.append({"severity": "critical", "category": "performance", "title": "CPU saturation", "message": f"CPU usage is {cpu:.1f}%.", "details": {"cpu_percent": cpu}})
    elif isinstance(cpu, (int, float)) and cpu >= 85:
        alerts.append({"severity": "warning", "category": "performance", "title": "High CPU usage", "message": f"CPU usage is {cpu:.1f}%.", "details": {"cpu_percent": cpu}})
    if isinstance(memory, (int, float)) and memory >= 95:
        alerts.append({"severity": "critical", "category": "memory", "title": "Memory pressure", "message": f"Memory usage is {memory:.1f}%.", "details": {"memory_percent": memory}})
    elif isinstance(memory, (int, float)) and memory >= 85:
        alerts.append({"severity": "warning", "category": "memory", "title": "High memory usage", "message": f"Memory usage is {memory:.1f}%.", "details": {"memory_percent": memory}})
    if isinstance(disk, (int, float)) and disk >= 95:
        alerts.append({"severity": "critical", "category": "storage", "title": "Disk almost full", "message": f"Disk usage is {disk:.1f}%.", "details": {"disk_percent": disk}})
    elif isinstance(disk, (int, float)) and disk >= 90:
        alerts.append({"severity": "warning", "category": "storage", "title": "Low disk space", "message": f"Disk usage is {disk:.1f}%.", "details": {"disk_percent": disk}})
    return alerts

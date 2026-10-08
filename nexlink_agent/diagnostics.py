"""Read-only diagnostics used by NEXLINK AI and the command center."""
from __future__ import annotations
import platform, socket, psutil
from .monitor import collect
from .remote import list_processes


def system_info() -> dict:
    metrics = collect()
    return {**metrics, "python": platform.python_version(), "hostname": socket.gethostname()}


def diagnostic_snapshot() -> dict:
    return {"system": system_info(), "processes": list_processes(25)}

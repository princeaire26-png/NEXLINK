"""Endpoint inventory collection. Values come from the operating system."""
from __future__ import annotations
import platform, socket, subprocess, shutil
import psutil
from datetime import datetime, timezone


def collect_inventory() -> dict:
    software = []
    # Cross-platform baseline. Windows registry inventory is intentionally optional.
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName,DisplayVersion,Publisher | ConvertTo-Json -Compress"], text=True, timeout=20)
            import json
            raw = json.loads(output or "[]")
            if isinstance(raw, dict): raw = [raw]
            software = [{"name": x.get("DisplayName"), "version": x.get("DisplayVersion") or "", "publisher": x.get("Publisher") or ""} for x in raw if x.get("DisplayName")]
        except Exception:
            software = []
    interfaces = {}
    for name, addrs in psutil.net_if_addrs().items():
        interfaces[name] = [{"family": str(a.family), "address": a.address, "netmask": a.netmask} for a in addrs]
    return {
        "hardware": {"cpu": platform.processor(), "machine": platform.machine(), "cores": psutil.cpu_count(logical=True), "memory_bytes": psutil.virtual_memory().total},
        "network": {"hostname": socket.gethostname(), "interfaces": interfaces},
        "software": software,
        "monitors": [],
        "printers": [],
        "usb": [],
        "services": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

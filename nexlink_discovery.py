"""LAN discovery for NEXLINK Server/Client.

Discovery is deliberately small and dependency-light: the server listens on a
UDP broadcast port and answers a signed-free, informational probe with its
HTTP API endpoint and local IPv4 addresses. Authentication/enrollment still
happens over the NEXLINK API; discovery never grants access by itself.
"""
from __future__ import annotations

import ipaddress
import json
import os
import platform
import socket
import threading
import time
from typing import Callable

DISCOVERY_CLIENT_INTERVAL = float(os.environ.get("NEXLINK_CLIENT_DISCOVERY_INTERVAL", "5"))

DISCOVERY_PORT = int(os.environ.get("NEXLINK_DISCOVERY_PORT", "39501"))
MAGIC = "NEXLINK-DISCOVERY-V1"
PROBE = {"magic": MAGIC, "type": "probe"}


def _local_ipv4_broadcasts() -> list[str]:
    broadcasts = {"255.255.255.255"}
    try:
        import psutil
        for _name, addresses in psutil.net_if_addrs().items():
            for addr in addresses:
                if getattr(addr, "family", None) != socket.AF_INET:
                    continue
                ip = getattr(addr, "address", "")
                mask = getattr(addr, "netmask", None)
                if not ip or ip.startswith("127.") or not mask:
                    continue
                try:
                    net = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
                    if net.broadcast_address.version == 4:
                        broadcasts.add(str(net.broadcast_address))
                except ValueError:
                    continue
    except Exception:
        pass
    return sorted(broadcasts)


def _local_ipv4_addresses() -> list[str]:
    values: list[str] = []
    try:
        import psutil
        for addresses in psutil.net_if_addrs().values():
            for addr in addresses:
                if getattr(addr, "family", None) == socket.AF_INET:
                    ip = getattr(addr, "address", "")
                    if ip and not ip.startswith("127.") and ip not in values:
                        values.append(ip)
    except Exception:
        pass
    return values


def _response(port: int) -> dict:
    ips = _local_ipv4_addresses()
    return {
        "magic": MAGIC,
        "type": "server",
        "hostname": platform.node(),
        "port": int(port),
        "ips": ips,
        "version": os.environ.get("NEXLINK_VERSION", "2.1.0"),
        "timestamp": int(time.time()),
    }


def discover_servers(timeout: float = 2.5, port: int = DISCOVERY_PORT) -> list[dict]:
    """Discover NEXLINK servers on the local LAN.

    Results are de-duplicated by IP/port and sorted with the most useful
    addresses first. This is LAN-only discovery; no Internet scan occurs.
    """
    found: dict[tuple[str, int], dict] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.25)
        payload = json.dumps(PROBE).encode("utf-8")
        for broadcast in _local_ipv4_broadcasts():
            try:
                sock.sendto(payload, (broadcast, port))
            except OSError:
                continue
        deadline = time.monotonic() + max(0.25, timeout)
        while time.monotonic() < deadline:
            try:
                raw, addr = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                item = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if item.get("magic") != MAGIC or item.get("type") != "server":
                continue
            try:
                api_port = int(item.get("port", 8000))
            except (TypeError, ValueError):
                api_port = 8000
            ips = list(item.get("ips") or [])
            if addr[0] not in ips:
                ips.insert(0, addr[0])
            for ip in ips:
                if not ip or ip.startswith("127."):
                    continue
                key = (ip, api_port)
                item_copy = dict(item)
                item_copy["ip"] = ip
                item_copy["url"] = f"http://{ip}:{api_port}"
                found[key] = item_copy
    finally:
        sock.close()
    return sorted(found.values(), key=lambda x: (x.get("hostname", "").lower(), x.get("ip", "")))


_discovered_clients: dict[str, dict] = {}
_discovered_lock = threading.Lock()

def get_discovered_clients(max_age: float = 20.0) -> list[dict]:
    """Return NEXLINK clients recently visible on the LAN.

    Discovery is informational only. A discovered client is NOT enrolled,
    approved, authenticated, or granted any server capability.
    """
    cutoff = time.time() - max_age
    with _discovered_lock:
        stale = [k for k, v in _discovered_clients.items() if float(v.get("timestamp", 0)) < cutoff]
        for k in stale:
            _discovered_clients.pop(k, None)
        return sorted((dict(v) for v in _discovered_clients.values()),
                      key=lambda x: (x.get("device_name", "").lower(), x.get("ip", "")))


class ClientAnnouncer:
    """Background LAN beacon emitted by a NEXLINK Client/Agent."""
    def __init__(self, device_id: str, device_name: str, version: str = "2.1.0", port: int = DISCOVERY_PORT):
        self.device_id = device_id
        self.device_name = device_name or platform.node()
        self.version = version
        self.port = port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "ClientAnnouncer":
        if self._thread and self._thread.is_alive():
            return self
        self._thread = threading.Thread(target=self._run, name="NEXLINK-Client-Discovery", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            while not self._stop.is_set():
                payload = {
                    "magic": MAGIC,
                    "type": "client",
                    "device_id": self.device_id,
                    "device_name": self.device_name,
                    "hostname": platform.node(),
                    "version": self.version,
                    "os": platform.platform(),
                    "timestamp": int(time.time()),
                }
                raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                for broadcast in _local_ipv4_broadcasts():
                    try:
                        sock.sendto(raw, (broadcast, self.port))
                    except OSError:
                        continue
                self._stop.wait(DISCOVERY_CLIENT_INTERVAL)
        finally:
            sock.close()


class DiscoveryResponder:
    """Background UDP responder owned by the NEXLINK Server process."""

    def __init__(self, api_port: int = 8000, port: int = DISCOVERY_PORT):
        self.api_port = api_port
        self.port = port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: Exception | None = None

    def start(self) -> "DiscoveryResponder":
        if self._thread and self._thread.is_alive():
            return self
        self._thread = threading.Thread(target=self._run, name="NEXLINK-LAN-Discovery", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.port))
            sock.settimeout(0.5)
            response = json.dumps(_response(self.api_port), separators=(",", ":")).encode("utf-8")
            while not self._stop.is_set():
                try:
                    raw, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    probe = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if probe.get("magic") != MAGIC:
                    continue
                if probe.get("type") == "probe":
                    try:
                        sock.sendto(response, addr)
                    except OSError:
                        continue
                    continue
                if probe.get("type") == "client":
                    device_id = str(probe.get("device_id") or "").strip()
                    if not device_id:
                        continue
                    item = dict(probe)
                    item["ip"] = addr[0]
                    item["last_seen"] = int(time.time())
                    with _discovered_lock:
                        _discovered_clients[device_id] = item
        except Exception as exc:
            self.error = exc
        finally:
            sock.close()

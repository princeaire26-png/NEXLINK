import asyncio
from pathlib import Path
import socket
import sys
import time
import uuid
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import nexlink_discovery as discovery
import server_launcher
from nexlink_discovery import ClientAnnouncer, DiscoveryResponder, discover_servers


def _free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_server_responder_answers_client_lan_discovery(monkeypatch):
    port = _free_udp_port()
    monkeypatch.setattr(discovery, "_local_ipv4_broadcasts", lambda: ["127.0.0.1"])
    monkeypatch.setattr(discovery, "_local_ipv4_addresses", lambda: ["192.0.2.10"])
    responder = DiscoveryResponder(api_port=8123, port=port).start()
    try:
        servers = discover_servers(timeout=1.0, port=port)
    finally:
        responder.stop()

    assert any(
        server["ip"] == "192.0.2.10"
        and server["url"] == "http://192.0.2.10:8123"
        and server["hostname"]
        for server in servers
    )


def test_client_announcer_is_visible_to_server_responder(monkeypatch):
    port = _free_udp_port()
    device_id = f"test-{uuid.uuid4().hex}"
    monkeypatch.setattr(discovery, "_local_ipv4_broadcasts", lambda: ["127.0.0.1"])
    monkeypatch.setattr(discovery, "DISCOVERY_CLIENT_INTERVAL", 0.05)
    responder = DiscoveryResponder(api_port=8000, port=port).start()
    announcer = ClientAnnouncer(
        device_id=device_id,
        device_name="LAN test client",
        version="test",
        port=port,
    ).start()
    clients = []
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            clients = [
                client for client in discovery.get_discovered_clients()
                if client["device_id"] == device_id
            ]
            if clients:
                break
            time.sleep(0.02)
    finally:
        announcer.stop()
        responder.stop()
        with discovery._discovered_lock:
            discovery._discovered_clients.pop(device_id, None)

    assert clients
    assert clients[0]["device_name"] == "LAN test client"
    assert clients[0]["ip"] == "127.0.0.1"


def test_server_uses_receipt_time_to_expire_untrusted_client_timestamps():
    now = int(time.time())
    recent_id = f"recent-{uuid.uuid4().hex}"
    stale_id = f"stale-{uuid.uuid4().hex}"
    with discovery._discovered_lock:
        discovery._discovered_clients[recent_id] = {
            "device_id": recent_id,
            "timestamp": 1,
            "last_seen": now,
        }
        discovery._discovered_clients[stale_id] = {
            "device_id": stale_id,
            "timestamp": now + 86400,
            "last_seen": now - 60,
        }
    try:
        recent = {
            client["device_id"]
            for client in discovery.get_discovered_clients(max_age=20)
        }
    finally:
        with discovery._discovered_lock:
            discovery._discovered_clients.pop(recent_id, None)
            discovery._discovered_clients.pop(stale_id, None)

    assert recent_id in recent
    assert stale_id not in recent


def test_agent_service_starts_and_stops_its_client_beacon(monkeypatch):
    from nexlink_agent import service as agent_service

    instances = []

    class StubAnnouncer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = False
            self.stopped = False
            instances.append(self)

        def start(self):
            self.started = True
            return self

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(agent_service, "ClientAnnouncer", StubAnnouncer)
    service = agent_service.AgentService(
        SimpleNamespace(server_url="", device_name="Test client", agent_version="2.1.0"),
        SimpleNamespace(device_id="device-123"),
    )

    async def no_network_run():
        await asyncio.sleep(0)

    monkeypatch.setattr(service, "_run", no_network_run)
    thread = service.start()
    thread.join(timeout=2)
    service.stop()

    assert not thread.is_alive()
    assert len(instances) == 1
    assert instances[0].started and instances[0].stopped
    assert instances[0].kwargs == {
        "device_id": "device-123",
        "device_name": "Test client",
        "version": "2.1.0",
    }


def test_discovery_firewall_rule_is_checked_even_if_api_rule_exists():
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if "show" in command:
            rule = command[-1]
            stdout = "LocalPort: 8000" if rule == "name=NEXLINK-Server-API" else ""
            return SimpleNamespace(stdout=stdout)
        return SimpleNamespace(stdout="")

    server_launcher._configure_api_firewall(platform_name="nt", run=fake_run)

    added_rules = [command for command, _kwargs in calls if "add" in command]
    assert len(added_rules) == 1
    assert "name=NEXLINK-LAN-Discovery" in added_rules[0]
    assert "protocol=UDP" in added_rules[0]
    assert "localport=39501" in added_rules[0]

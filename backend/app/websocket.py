"""NEXLINK authenticated device transport and remote-control fan-out."""
from __future__ import annotations
import asyncio
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.crypto.ed25519 import verify_ed25519_signature
from app.database import async_session_maker
from app.models import AuditEvent, Device, DeviceConnection, DeviceIdentity, DeviceMetric, DeviceAlert, DeviceSoftware, Automation, AutomationRun
from app.platform.alerts import evaluate_metrics
from app.platform.automation import matches_trigger
from app.security import verify_token

router = APIRouter()
HEARTBEAT_TIMEOUT = 90
AUTH_TIMEOUT = 30
AUTH_CLOCK_SKEW = 60
CHALLENGE_TTL = 60


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict] = {}
        self.control_connections: dict[str, dict] = {}
        self.session_controls: dict[str, set[str]] = {}

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = {
            "websocket": websocket, "device_id": None, "device_db_id": None,
            "authenticated": False, "connected_at": utcnow(), "last_heartbeat": utcnow(),
            "challenge_id": None, "challenge_data": None, "challenge_expires_at": None,
        }

    def disconnect(self, connection_id: str):
        self.active_connections.pop(connection_id, None)

    def get_connection(self, connection_id: str) -> Optional[dict]:
        return self.active_connections.get(connection_id)

    def update_heartbeat(self, connection_id: str):
        conn = self.active_connections.get(connection_id)
        if conn:
            conn["last_heartbeat"] = utcnow()

    async def close_device_connections(self, device_id: str, reason: str = "Device revoked") -> None:
        for conn in list(self.active_connections.values()):
            if conn.get("device_id") == device_id:
                try:
                    await conn["websocket"].close(code=4005, reason=reason)
                except Exception:
                    pass
        for cid, control in list(self.control_connections.items()):
            if control.get("device_id") == device_id:
                try:
                    await control["websocket"].close(code=4005, reason=reason)
                except Exception:
                    pass

    async def send_action(self, device_id: str, request_id: str, action: str, params: dict) -> bool:
        delivered = False
        for conn in list(self.active_connections.values()):
            if conn.get("device_id") == device_id and conn.get("authenticated"):
                try:
                    await conn["websocket"].send_json({"type": "action_request", "request_id": request_id, "action": action, "params": params})
                    delivered = True
                except Exception:
                    pass
        return delivered

    async def attach_control(self, websocket: WebSocket, connection_id: str, user_id: str, session_id: str, device_id: str):
        await websocket.accept()
        self.control_connections[connection_id] = {"websocket": websocket, "user_id": user_id, "session_id": session_id, "device_id": device_id}
        self.session_controls.setdefault(session_id, set()).add(connection_id)

    def detach_control(self, connection_id: str):
        control = self.control_connections.pop(connection_id, None)
        if not control:
            return
        session_id = control.get("session_id")
        if session_id in self.session_controls:
            self.session_controls[session_id].discard(connection_id)
            if not self.session_controls[session_id]:
                self.session_controls.pop(session_id, None)

    async def broadcast_session(self, session_id: str, message: dict):
        for cid in list(self.session_controls.get(session_id, set())):
            control = self.control_connections.get(cid)
            if not control:
                continue
            try:
                await control["websocket"].send_json(message)
            except Exception:
                self.detach_control(cid)

    async def send_control_action(self, session_id: str, action: str, params: dict) -> bool:
        controls = self.session_controls.get(session_id, set())
        for cid in controls:
            control = self.control_connections.get(cid)
            if control:
                return await self.send_action(control["device_id"], str(uuid.uuid4()), action, {**params, "session_id": session_id})
        return False


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id)
    auth_timeout_task = asyncio.create_task(handle_auth_timeout(connection_id, websocket))
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=HEARTBEAT_TIMEOUT)
                conn = manager.get_connection(connection_id)
                if not conn:
                    break
                if not conn["authenticated"]:
                    if message.get("type") == "hello":
                        await handle_hello(websocket, message, connection_id, conn)
                    elif message.get("type") == "auth_proof":
                        if await handle_auth_proof(websocket, message, connection_id, conn):
                            auth_timeout_task.cancel()
                    else:
                        await websocket.send_json({"type": "error", "message": "Authentication required"})
                else:
                    manager.update_heartbeat(connection_id)
                    await handle_authenticated_message(websocket, message, connection_id, conn)
            except asyncio.TimeoutError:
                await websocket.close(code=4002, reason="Heartbeat timeout")
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"WebSocket error: {exc}")
    finally:
        auth_timeout_task.cancel()
        conn = manager.get_connection(connection_id)
        if conn and conn["authenticated"]:
            await handle_disconnect(connection_id, conn)
        manager.disconnect(connection_id)


@router.websocket("/ws/control/{session_id}")
async def control_websocket(websocket: WebSocket, session_id: str):
    """User-side remote session channel. Authentication is the same JWT/session model as REST."""
    connection_id = str(uuid.uuid4())
    await websocket.accept()
    attached = False
    try:
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=20)
        if auth.get("type") != "authenticate":
            await websocket.close(code=4401, reason="Authentication required")
            return
        payload = verify_token(auth.get("access_token", ""))
        if not payload or payload.get("type") != "access":
            await websocket.close(code=4401, reason="Invalid access token")
            return
        user_id = str(payload.get("sub", ""))
        sid = str(payload.get("sid", ""))
        async with async_session_maker() as db:
            from app.models import Session as UserSession, ConnectionSession, User
            user = (await db.execute(select(User).where(User.id == uuid.UUID(user_id), User.active.is_(True)))).scalar_one_or_none()
            user_session = (await db.execute(select(UserSession).where(UserSession.id == uuid.UUID(sid), UserSession.user_id == uuid.UUID(user_id), UserSession.revoked_at.is_(None), UserSession.expires_at > utcnow()))).scalar_one_or_none()
            remote_session = (await db.execute(select(ConnectionSession).where(ConnectionSession.id == uuid.UUID(session_id), ConnectionSession.user_id == uuid.UUID(user_id), ConnectionSession.status == "active"))).scalar_one_or_none()
            if not user or not user_session or not remote_session:
                await websocket.close(code=4403, reason="Session not active")
                return
            device = (await db.execute(select(Device).where(Device.id == remote_session.device_id))).scalar_one_or_none()
            if not device or not device.approved or device.status == "revoked":
                await websocket.close(code=4403, reason="Device unavailable")
                return
            device_wire_id = device.device_id
        await manager.attach_control(websocket, connection_id, user_id, session_id, device_wire_id)
        manager.control_connections[connection_id]["role"] = user.role
        attached = True
        await manager.send_control_action(session_id, "remote.start", {"quality": "adaptive"})
        await manager.broadcast_session(session_id, {"type": "session_state", "state": "connecting", "session_id": session_id})
        while True:
            message = await websocket.receive_json()
            typ = message.get("type")
            if typ == "ping":
                await websocket.send_json({"type": "pong", "timestamp": int(time.time() * 1000)})
            elif typ == "input_event":
                await manager.send_control_action(session_id, "remote.input", message.get("payload") or {})
            elif typ == "clipboard_sync":
                await manager.send_control_action(session_id, "remote.clipboard", message.get("payload") or {})
            elif typ == "file_transfer_request":
                payload = message.get("payload") or {}
                direction = payload.get("direction")
                if direction == "upload" and manager.control_connections.get(connection_id, {}).get("role") not in {"owner", "admin"}:
                    await websocket.send_json({"type":"error","message":"File upload requires administrator authorization"}); continue
                action = "remote.file.download" if direction == "download" else "remote.file.upload"
                if direction == "upload": payload["_authorized"] = True
                if direction not in {"download", "upload"}:
                    await websocket.send_json({"type":"error","message":"Invalid file transfer direction"}); continue
                await manager.send_control_action(session_id, action, payload)
            elif typ == "file_transfer_data":
                if manager.control_connections.get(connection_id, {}).get("role") not in {"owner", "admin"}:
                    await websocket.send_json({"type":"error","message":"File upload requires administrator authorization"}); continue
                payload = {**(message.get("payload") or {}), "_authorized": True}
                await manager.send_control_action(session_id, "remote.file.upload", payload)
            elif typ == "session_end":
                await manager.send_control_action(session_id, "remote.stop", {})
                break
            else:
                await websocket.send_json({"type": "error", "message": f"Unsupported control message: {typ}"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        manager.detach_control(connection_id)
        try:
            if not attached:
                return
            async with async_session_maker() as db:
                from app.models import ConnectionSession
                remote_session = (await db.execute(select(ConnectionSession).where(ConnectionSession.id == uuid.UUID(session_id), ConnectionSession.status == "active"))).scalar_one_or_none()
                if remote_session:
                    remote_session.status = "ended"; remote_session.ended_at = utcnow(); remote_session.duration = max(0, int((remote_session.ended_at - remote_session.started_at).total_seconds()))
                    await db.commit()
        except Exception:
            pass


async def handle_auth_timeout(connection_id: str, websocket: WebSocket):
    try:
        await asyncio.sleep(AUTH_TIMEOUT)
        conn = manager.get_connection(connection_id)
        if conn and not conn["authenticated"]:
            await websocket.send_json({"type": "error", "message": "Authentication timeout"})
            await websocket.close(code=4001, reason="Authentication timeout")
    except Exception:
        return


async def handle_hello(websocket: WebSocket, message: dict, connection_id: str, conn: dict):
    device_id, public_key, timestamp, signature = message.get("device_id"), message.get("public_key"), message.get("timestamp"), message.get("signature")
    if not all([device_id, public_key, timestamp, signature]):
        await websocket.close(code=4007, reason="Invalid hello message"); return
    if abs(int(time.time()) - int(timestamp)) > AUTH_CLOCK_SKEW:
        await websocket.close(code=4008, reason="Stale hello"); return
    hello_data = f"{device_id}:{public_key}:{int(timestamp)}".encode()
    if not verify_ed25519_signature(hello_data, signature, public_key):
        await websocket.close(code=4009, reason="Invalid hello signature"); return
    async with async_session_maker() as db:
        device = (await db.execute(select(Device).where(Device.device_id == device_id))).scalar_one_or_none()
        if not device or not device.approved or device.status == "revoked":
            await websocket.send_json({"type": "auth_rejected", "reason": "Unknown, unapproved, or revoked device"})
            await websocket.close(code=4004, reason="Device unavailable"); return
        identity = (await db.execute(select(DeviceIdentity).where(DeviceIdentity.device_id == device.id, DeviceIdentity.active.is_(True)))).scalar_one_or_none()
        if not identity or identity.public_key != public_key:
            await websocket.close(code=4006, reason="Public key mismatch"); return
        conn.update({"device_id": device_id, "device_db_id": str(device.id), "challenge_id": str(uuid.uuid4()), "challenge_data": secrets.token_hex(32), "challenge_expires_at": int((time.time() + CHALLENGE_TTL) * 1000)})
        await websocket.send_json({"type": "auth_challenge", "challenge_id": conn["challenge_id"], "challenge": conn["challenge_data"], "expires_at": conn["challenge_expires_at"]})


async def handle_auth_proof(websocket: WebSocket, message: dict, connection_id: str, conn: dict) -> bool:
    challenge_id, signature, timestamp = message.get("challenge_id"), message.get("signature"), message.get("timestamp")
    if not challenge_id or not signature or timestamp is None or challenge_id != conn.get("challenge_id"):
        await websocket.close(code=4010, reason="Invalid auth proof"); return False
    if abs(int(time.time()) - int(timestamp)) > AUTH_CLOCK_SKEW:
        await websocket.close(code=4012, reason="Stale auth proof"); return False
    if not conn.get("challenge_data") or int(time.time() * 1000) > conn["challenge_expires_at"]:
        await websocket.close(code=4013, reason="Challenge expired"); return False
    async with async_session_maker() as db:
        identity = (await db.execute(select(DeviceIdentity).where(DeviceIdentity.device_id == conn["device_db_id"], DeviceIdentity.active.is_(True)))).scalar_one_or_none()
        if not identity or not verify_ed25519_signature(conn["challenge_data"].encode(), signature, identity.public_key):
            db.add(AuditEvent(id=uuid.uuid4(), event_type="auth_failed", actor_id=uuid.UUID(conn["device_db_id"]), actor_type="device", target_type="device", target_id=uuid.UUID(conn["device_db_id"]), action="websocket_auth", result="failure", details={"reason": "invalid_signature", "connection_id": connection_id}))
            await db.commit(); await websocket.close(code=4014, reason="Invalid signature"); return False
        conn["challenge_data"] = None; conn["authenticated"] = True; conn["last_heartbeat"] = utcnow()
        session_token = secrets.token_urlsafe(32)
        db.add(DeviceConnection(id=uuid.uuid4(), device_id=uuid.UUID(conn["device_db_id"]), connection_id=connection_id, session_token=session_token, status="active"))
        device = (await db.execute(select(Device).where(Device.id == uuid.UUID(conn["device_db_id"]))).scalar_one())
        device.status = "online"; device.last_seen_at = utcnow()
        db.add(AuditEvent(id=uuid.uuid4(), event_type="auth_success", actor_id=device.id, actor_type="device", target_type="device", target_id=device.id, action="websocket_auth", result="success", details={"connection_id": connection_id}))
        await db.commit()
        await websocket.send_json({"type": "auth_accepted", "session_token": session_token, "expires_at": (utcnow() + timedelta(hours=24)).isoformat()})
        return True


async def handle_authenticated_message(websocket: WebSocket, message: dict, connection_id: str, conn: dict):
    msg_type = message.get("type")
    if msg_type == "ping":
        async with async_session_maker() as db:
            connection = (await db.execute(select(DeviceConnection).where(DeviceConnection.connection_id == connection_id, DeviceConnection.status == "active"))).scalar_one_or_none()
            if connection:
                connection.last_heartbeat = utcnow(); await db.commit()
        await websocket.send_json({"type": "pong", "timestamp": int(time.time() * 1000)})
    elif msg_type == "metrics_report":
        await handle_metrics_report(conn["device_db_id"], message.get("payload") or {})
    elif msg_type == "inventory_report":
        await handle_inventory_report(conn["device_db_id"], message.get("payload") or {})
    elif msg_type in {"screen_frame", "screen_info", "action_result", "terminal_output", "clipboard_sync", "file_transfer_data", "file_transfer_complete"}:
        session_id = str((message.get("payload") or {}).get("session_id", ""))
        if session_id:
            await manager.broadcast_session(session_id, message)
        if msg_type == "action_result":
            await handle_action_result(conn["device_db_id"], message)
    elif msg_type == "status_update":
        return
    else:
        await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})


async def handle_metrics_report(device_db_id: str, metrics: dict):
    async with async_session_maker() as db:
        db.add(DeviceMetric(id=uuid.uuid4(), device_id=uuid.UUID(device_db_id), cpu_percent=metrics.get("cpu_percent"), cpu_cores=metrics.get("cpu_cores"), memory_total_bytes=metrics.get("memory_total_bytes"), memory_used_bytes=metrics.get("memory_used_bytes"), memory_percent=metrics.get("memory_percent"), disk_total_bytes=metrics.get("disk_total_bytes"), disk_used_bytes=metrics.get("disk_used_bytes"), disk_percent=metrics.get("disk_percent"), uptime_seconds=metrics.get("uptime_seconds"), hostname=metrics.get("hostname"), os_name=metrics.get("os_name"), os_version=metrics.get("os_version"), architecture=metrics.get("architecture")))
        device = (await db.execute(select(Device).where(Device.id == uuid.UUID(device_db_id)))).scalar_one_or_none()
        if device:
            device.last_seen_at = utcnow(); device.last_metrics_at = utcnow(); device.metadata_ = {**(device.metadata_ or {}), "latest_metrics": metrics}
            for alert in evaluate_metrics(metrics):
                existing = (await db.execute(select(DeviceAlert).where(DeviceAlert.device_id == device.id, DeviceAlert.category == alert["category"], DeviceAlert.title == alert["title"], DeviceAlert.state == "open"))).scalar_one_or_none()
                if not existing:
                    db.add(DeviceAlert(id=uuid.uuid4(), device_id=device.id, **alert))
            if device.organization_id:
                result = await db.execute(select(Automation).where(Automation.organization_id == device.organization_id, Automation.enabled.is_(True)))
                event = {"event": "metrics", **metrics}
                for automation in result.scalars().all():
                    match = matches_trigger(automation.trigger_config or {}, event)
                    if not match.matched:
                        continue
                    run = AutomationRun(id=uuid.uuid4(), automation_id=automation.id, status="running", result={"trigger": event})
                    db.add(run)
                    for action in automation.actions or []:
                        kind = action.get("type")
                        if kind == "create_alert":
                            db.add(DeviceAlert(id=uuid.uuid4(), device_id=device.id, severity=action.get("severity", "warning"), category="automation", title=action.get("title", automation.name), message=action.get("message", f"Automation '{automation.name}' matched."), state="open", details={"automation_id": str(automation.id)}))
                        elif kind == "request_health_check":
                            await manager.send_action(device.device_id, str(uuid.uuid4()), "ai.get_system_info", {})
                        elif kind == "notify":
                            db.add(AuditEvent(id=uuid.uuid4(), event_type="automation_notification", actor_type="system", target_type="device", target_id=device.id, action="notify", result="success", details={"automation_id": str(automation.id), "message": action.get("message", automation.name)}))
                    run.status = "completed"; run.completed_at = utcnow(); automation.last_run_at = utcnow()
        await db.commit()


async def handle_inventory_report(device_db_id: str, payload: dict):
    async with async_session_maker() as db:
        device = (await db.execute(select(Device).where(Device.id == uuid.UUID(device_db_id)))).scalar_one_or_none()
        if not device:
            return
        device.metadata_ = {**(device.metadata_ or {}), "inventory": payload}
        for item in payload.get("software", []):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            version = str(item.get("version") or "")
            existing = (await db.execute(select(DeviceSoftware).where(DeviceSoftware.device_id == device.id, DeviceSoftware.name == name, DeviceSoftware.version == version))).scalar_one_or_none()
            if not existing:
                db.add(DeviceSoftware(device_id=device.id, name=name, version=version, publisher=str(item.get("publisher") or ""), install_date=item.get("install_date"), metadata_=item))
        await db.commit()


async def handle_action_result(device_db_id: str, message: dict):
    async with async_session_maker() as db:
        db.add(AuditEvent(id=uuid.uuid4(), event_type="device_action_result", actor_id=uuid.UUID(device_db_id), actor_type="device", target_type="device", target_id=uuid.UUID(device_db_id), action=str(message.get("action", "device_action")), result="success" if message.get("success") else "failure", details={"request_id": message.get("request_id"), "result": message.get("result")}))
        await db.commit()


async def handle_disconnect(connection_id: str, conn: dict):
    async with async_session_maker() as db:
        device = (await db.execute(select(Device).where(Device.id == uuid.UUID(conn["device_db_id"])))).scalar_one_or_none()
        if device and device.status != "revoked":
            device.status = "offline"; device.last_seen_at = utcnow()
        connection = (await db.execute(select(DeviceConnection).where(DeviceConnection.connection_id == connection_id))).scalar_one_or_none()
        if connection:
            connection.status = "disconnected"; connection.disconnected_at = utcnow()
        await db.commit()

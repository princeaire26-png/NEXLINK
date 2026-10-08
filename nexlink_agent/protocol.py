"""NEXLINK wire protocol implemented entirely in Python."""
from __future__ import annotations
import json, uuid
from dataclasses import dataclass, asdict
from typing import Any

PROTOCOL_VERSION = "1.0.0"

KNOWN_TYPES = {
    "hello","hello_ack","auth_challenge","auth_proof","auth_accepted","auth_rejected",
    "ping","pong","status_update","metrics_report","inventory_report","metrics_request",
    "action_request","action_result","disconnect","error",
    "session_start","session_start_ack","session_end",
    "session_create","session_accept","session_reject","session_terminate",
    "screen_info","screen_keyframe","screen_frame","screen_frame_ack",
    "input_event","clipboard_sync","file_transfer_request","file_transfer_data",
    "file_transfer_complete","file_transfer_cancel","terminal_command","terminal_output",
    "terminal_exit","ai_tool_request","ai_tool_response",
}

@dataclass
class Envelope:
    type: str
    payload: dict[str, Any] | None = None
    message_id: str = ""
    version: str = PROTOCOL_VERSION

    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if self.payload is None:
            self.payload = {}

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "payload": self.payload, "message_id": self.message_id, "version": self.version}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Envelope":
        return cls(type=value["type"], payload=value.get("payload") or {}, message_id=value.get("message_id",""), version=value.get("version",PROTOCOL_VERSION))

    @classmethod
    def from_json(cls, value: str) -> "Envelope":
        return cls.from_dict(json.loads(value))

    def validate(self) -> None:
        if self.type not in KNOWN_TYPES:
            raise ValueError(f"Unknown message type: {self.type}")

"""NEXLINK endpoint configuration and connection normalization."""
from __future__ import annotations
import json, os, platform
from pathlib import Path
from dataclasses import dataclass, asdict


def app_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NEXLINK"


def normalize_http_url(value: str) -> str:
    s = value.strip().rstrip("/")
    if s.startswith(("http://", "https://")):
        return s
    if s.startswith(("ws://", "wss://")):
        return ("http://" if s.startswith("ws://") else "https://") + s.split("://", 1)[1]
    return "http://" + s


def normalize_ws_url(value: str) -> str:
    s = value.strip().rstrip("/")
    if s.startswith("http://"):
        s = "ws://" + s[7:]
    elif s.startswith("https://"):
        s = "wss://" + s[8:]
    elif not s.startswith(("ws://", "wss://")):
        s = "ws://" + s
    if not s.endswith("/ws"):
        s += "/ws"
    return s


@dataclass
class AgentConfig:
    server_url: str = ""
    device_name: str = platform.node()
    identity_passphrase: str = ""
    enrolled: bool = False
    agent_version: str = "2.1.0"

    @classmethod
    def load(cls) -> "AgentConfig":
        p = app_dir() / "agent.json"
        if not p.exists():
            return cls()
        try:
            cfg = cls(**json.loads(p.read_text(encoding="utf-8")))
            if cfg.server_url:
                cfg.server_url = normalize_http_url(cfg.server_url)
            return cfg
        except Exception:
            return cls()

    def save(self) -> None:
        p = app_dir() / "agent.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        self.server_url = normalize_http_url(self.server_url) if self.server_url else ""
        p.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @property
    def http_url(self) -> str:
        return normalize_http_url(self.server_url)

    @property
    def ws_url(self) -> str:
        return normalize_ws_url(self.server_url)


def identity_path() -> Path:
    return app_dir() / "identity.json"

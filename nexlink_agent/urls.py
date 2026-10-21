"""Normalize the server address for HTTP API and device WebSocket traffic."""
from __future__ import annotations

from urllib.parse import SplitResult, urlsplit, urlunsplit


def _server_parts(value: str) -> tuple[SplitResult, str]:
    raw = value.strip().rstrip("/")
    if not raw:
        raise ValueError("Enter a NEXLINK server address.")
    if "://" not in raw:
        raw = f"http://{raw}"

    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https", "ws", "wss"}:
        raise ValueError("Use an http://, https://, ws://, or wss:// server address.")
    if not parts.netloc or not parts.hostname:
        raise ValueError("The NEXLINK server address must include a host name or IP address.")
    if parts.username or parts.password:
        raise ValueError("Do not include a user name or password in the server address.")
    if parts.query or parts.fragment:
        raise ValueError("The NEXLINK server address cannot include a query or fragment.")
    try:
        parts.port
    except ValueError as exc:
        raise ValueError("The server address contains an invalid port.") from exc

    path = parts.path.rstrip("/")
    if path == "/ws":
        path = ""
    elif path.endswith("/ws"):
        path = path[:-3].rstrip("/")
    return parts, path


def http_base(value: str) -> str:
    """Return an HTTP(S) API base URL, accepting bare host:port and WS URLs."""
    parts, path = _server_parts(value)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme.lower(), parts.scheme.lower())
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def websocket_base(value: str) -> str:
    """Return the authenticated device WebSocket endpoint ending in /ws."""
    parts, path = _server_parts(value)
    scheme = {"http": "ws", "https": "wss"}.get(parts.scheme.lower(), parts.scheme.lower())
    return urlunsplit((scheme, parts.netloc, f"{path}/ws", "", ""))

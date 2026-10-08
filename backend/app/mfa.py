"""Dependency-free TOTP implementation for optional NEXLINK MFA."""
from __future__ import annotations
import base64, hashlib, hmac, secrets, struct, time


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _counter(secret: str, timestamp: int | None = None) -> int:
    return int((timestamp or int(time.time())) // 30)


def generate_code(secret: str, timestamp: int | None = None) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    msg = struct.pack(">Q", _counter(secret, timestamp))
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{number % 1_000_000:06d}"


def verify_code(secret: str, code: str, window: int = 1) -> bool:
    if not code or len(code) != 6 or not code.isdigit():
        return False
    now = int(time.time())
    return any(hmac.compare_digest(generate_code(secret, now + step * 30), code) for step in range(-window, window + 1))


def provisioning_uri(secret: str, email: str, issuer: str = "NEXLINK") -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"

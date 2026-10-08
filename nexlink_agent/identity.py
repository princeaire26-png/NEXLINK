"""Ed25519 device identity storage for the Python NEXLINK agent."""
from __future__ import annotations
import base64, hashlib, json, os, secrets
from pathlib import Path
from nacl.signing import SigningKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

class DeviceIdentity:
    VERSION = 3
    def __init__(self, signing_key: SigningKey, created_at: str | None = None):
        self.signing_key = signing_key
        self.created_at = created_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        self.device_id = self.derive_device_id(self.public_key_bytes())

    @staticmethod
    def derive_device_id(public_key: bytes) -> str:
        return "dev_" + hashlib.sha256(b"nexlink-device-v1:" + public_key).hexdigest()[:32]

    @staticmethod
    def public_key_hash(public_key: bytes) -> str:
        return hashlib.sha256(b"nexlink-pubkey-hash-v1:" + public_key).hexdigest()

    @property
    def public_key_bytes(self) -> bytes:
        return bytes(self.signing_key.verify_key)

    @property
    def public_key_hex(self) -> str:
        return self.public_key_bytes.hex()

    def sign(self, data: bytes) -> bytes:
        return self.signing_key.sign(data).signature

    @staticmethod
    def _key(passphrase: str, salt: bytes) -> bytes:
        kdf=PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
        return kdf.derive(passphrase.encode())

    def save(self, path: Path, passphrase: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        salt=secrets.token_bytes(32); nonce=secrets.token_bytes(12)
        encrypted=AESGCM(self._key(passphrase,salt)).encrypt(nonce, bytes(self.signing_key), None)
        data={"version":self.VERSION,"device_id":self.device_id,"encrypted_private_key":base64.b64encode(encrypted).decode(),
              "nonce":base64.b64encode(nonce).decode(),"salt":base64.b64encode(salt).decode(),
              "public_key_hash":self.public_key_hash(self.public_key_bytes),"created_at":self.created_at}
        path.write_text(json.dumps(data,indent=2),encoding="utf-8")

    @classmethod
    def load(cls,path:Path,passphrase:str)->"DeviceIdentity":
        d=json.loads(path.read_text(encoding="utf-8"))
        if d.get("version") != cls.VERSION:
            raise ValueError("Unsupported Python identity version")
        salt=base64.b64decode(d["salt"]); nonce=base64.b64decode(d["nonce"]); ct=base64.b64decode(d["encrypted_private_key"])
        raw=AESGCM(cls._key(passphrase,salt)).decrypt(nonce,ct,None)
        obj=cls(SigningKey(raw),d.get("created_at"))
        if obj.device_id != d["device_id"] or obj.public_key_hash(obj.public_key_bytes) != d.get("public_key_hash"):
            raise ValueError("Identity integrity check failed")
        return obj

    @classmethod
    def load_or_create(cls,path:Path,passphrase:str)->"DeviceIdentity":
        if path.exists():
            return cls.load(path,passphrase)
        obj=cls(SigningKey.generate()); obj.save(path,passphrase); return obj

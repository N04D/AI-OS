from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
from tempfile import NamedTemporaryFile
import threading
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..types import InvalidKey
from ..types import NotInitialized
from ..types import SecretKey
from ..types import SecretValue
from ..types import SecretsError


MAGIC = b"AIOSSEC1"
FORMAT_VERSION = 1
DEFAULT_SCRYPT_N = 2**14
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1
DEFAULT_PBKDF2_ITERATIONS = 600_000


class EncryptedStoreBackend:
    backend_name = "encrypted_store"

    def __init__(self, *, store_path: Path) -> None:
        self.store_path = store_path
        self._lock = threading.RLock()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.store_path.parent, 0o700)

    def is_available(self) -> bool:
        return True

    def is_initialized(self) -> bool:
        return self.store_path.exists()

    def init(self, **kwargs: object) -> None:
        passphrase = str(kwargs.get("passphrase") or "")
        if not passphrase:
            raise SecretsError("Passphrase is required to initialize fallback store")
        with self._lock:
            if self.is_initialized():
                raise SecretsError("Fallback store already initialized")
            self._write_payload({}, passphrase)

    def set(self, key: SecretKey, value: SecretValue, *, overwrite: bool = False, passphrase: str | None = None) -> None:
        if not passphrase:
            raise NotInitialized("Fallback store access requires passphrase")
        with self._lock:
            payload = self._read_payload(passphrase)
            k = key.as_str()
            if not overwrite and k in payload:
                raise InvalidKey(f"Secret '{k}' already exists; use overwrite=True")
            payload[k] = base64.b64encode(value.as_bytes()).decode("ascii")
            self._write_payload(payload, passphrase)

    def get(self, key: SecretKey, *, passphrase: str | None = None) -> SecretValue | None:
        if not passphrase:
            raise NotInitialized("Fallback store access requires passphrase")
        with self._lock:
            payload = self._read_payload(passphrase)
        encoded = payload.get(key.as_str())
        if encoded is None:
            return None
        return SecretValue(base64.b64decode(encoded.encode("ascii")))

    def delete(self, key: SecretKey, *, passphrase: str | None = None) -> None:
        if not passphrase:
            raise NotInitialized("Fallback store access requires passphrase")
        with self._lock:
            payload = self._read_payload(passphrase)
            payload.pop(key.as_str(), None)
            self._write_payload(payload, passphrase)

    def list(self, prefix: str | None = None, *, passphrase: str | None = None) -> list[SecretKey]:
        if not passphrase:
            raise NotInitialized("Fallback store access requires passphrase")
        with self._lock:
            payload = self._read_payload(passphrase)
        out: list[SecretKey] = []
        for raw in sorted(payload.keys()):
            if prefix and not raw.startswith(prefix):
                continue
            try:
                out.append(SecretKey.parse(raw))
            except InvalidKey:
                continue
        return out

    def rotate_passphrase(self, old: str, new: str) -> None:
        with self._lock:
            payload = self._read_payload(old)
            self._write_payload(payload, new)

    def _build_aad(self) -> bytes:
        uid = os.getuid() if hasattr(os, "getuid") else 0
        aad = {
            "v": FORMAT_VERSION,
            "hostname": socket.gethostname(),
            "uid": uid,
        }
        return json.dumps(aad, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _derive_key(self, passphrase: str, salt: bytes, kdf: dict[str, Any]) -> bytes:
        encoded = passphrase.encode("utf-8")
        try:
            if kdf.get("name") == "scrypt":
                return hashlib.scrypt(
                    encoded,
                    salt=salt,
                    n=int(kdf.get("n", DEFAULT_SCRYPT_N)),
                    r=int(kdf.get("r", DEFAULT_SCRYPT_R)),
                    p=int(kdf.get("p", DEFAULT_SCRYPT_P)),
                    dklen=32,
                )
        except (ValueError, AttributeError):
            pass
        iterations = int(kdf.get("iterations", DEFAULT_PBKDF2_ITERATIONS))
        return hashlib.pbkdf2_hmac("sha256", encoded, salt, iterations, dklen=32)

    def _encode_file(self, *, nonce: bytes, salt: bytes, ciphertext: bytes, kdf: dict[str, Any]) -> bytes:
        header = {
            "version": FORMAT_VERSION,
            "kdf": kdf,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "meta": {"cipher": "AES-256-GCM"},
        }
        header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + ciphertext

    def _decode_file(self, blob: bytes) -> tuple[dict[str, Any], bytes]:
        if len(blob) < len(MAGIC) + 4 or not blob.startswith(MAGIC):
            raise NotInitialized("Fallback store not initialized or invalid format")
        start = len(MAGIC)
        (header_len,) = struct.unpack(">I", blob[start : start + 4])
        header_start = start + 4
        header_end = header_start + header_len
        if len(blob) < header_end:
            raise SecretsError("Encrypted store corrupted: incomplete header")
        header = json.loads(blob[header_start:header_end].decode("utf-8"))
        ciphertext = blob[header_end:]
        return header, ciphertext

    def _read_payload(self, passphrase: str) -> dict[str, str]:
        if not self.is_initialized():
            raise NotInitialized("Fallback store is not initialized. Run 'aiosctl secrets init-fallback'.")
        blob = self.store_path.read_bytes()
        header, ciphertext = self._decode_file(blob)
        salt = base64.b64decode(header["salt"].encode("ascii"))
        nonce = base64.b64decode(header["nonce"].encode("ascii"))
        kdf = dict(header.get("kdf") or {})
        key = self._derive_key(passphrase, salt, kdf)
        try:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, self._build_aad())
        except InvalidTag as exc:
            raise SecretsError("Unable to decrypt fallback store: invalid passphrase or corrupted file") from exc
        finally:
            key = b"\x00" * len(key)
        payload = json.loads(plaintext.decode("utf-8"))
        if not isinstance(payload, dict):
            raise SecretsError("Encrypted payload is invalid")
        return {str(k): str(v) for k, v in payload.items()}

    def _atomic_write_bytes(self, data: bytes) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.store_path.parent, 0o700)
        with NamedTemporaryFile(prefix="store.", suffix=".tmp", dir=str(self.store_path.parent), delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self.store_path)
        os.chmod(self.store_path, 0o600)

    def _write_payload(self, payload: dict[str, str], passphrase: str) -> None:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        kdf: dict[str, Any] = {"name": "scrypt", "n": DEFAULT_SCRYPT_N, "r": DEFAULT_SCRYPT_R, "p": DEFAULT_SCRYPT_P}
        key = self._derive_key(passphrase, salt, kdf)
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, self._build_aad())
        finally:
            key = b"\x00" * len(key)
        data = self._encode_file(nonce=nonce, salt=salt, ciphertext=ciphertext, kdf=kdf)
        self._atomic_write_bytes(data)

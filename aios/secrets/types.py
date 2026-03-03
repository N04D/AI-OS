from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol


KEY_PATTERN = re.compile(r"^[a-z0-9._-]{1,128}$")


class SecretsError(RuntimeError):
    """Base error for all secret subsystem failures."""


class BackendUnavailable(SecretsError):
    """Raised when a backend cannot be used in the current environment."""


class NotInitialized(SecretsError):
    """Raised when fallback encrypted store is not initialized."""


class AccessDenied(SecretsError):
    """Raised when access policy denies secret retrieval."""


class InvalidKey(SecretsError):
    """Raised when a secret key does not satisfy validation rules."""


@dataclass(frozen=True)
class SecretKey:
    namespace: str
    name: str

    @classmethod
    def parse(cls, raw: str) -> "SecretKey":
        key = (raw or "").strip()
        if not key or key.startswith(".") or ".." in key or len(key) > 128:
            raise InvalidKey("Key must be non-empty, <=128 chars, no leading dot, no double dots")
        if not KEY_PATTERN.fullmatch(key):
            raise InvalidKey("Key can only contain [a-z0-9._-]")
        if "." not in key:
            raise InvalidKey("Key must have format '<domain>.<name>'")
        namespace, name = key.split(".", 1)
        if not namespace or not name:
            raise InvalidKey("Key must have non-empty domain and name")
        return cls(namespace=namespace, name=name)

    def as_str(self) -> str:
        return f"{self.namespace}.{self.name}"

    def __str__(self) -> str:
        return self.as_str()


class SecretValue:
    """Secret wrapper that avoids accidental repr leakage."""

    __slots__ = ("_raw",)

    def __init__(self, value: str | bytes) -> None:
        if isinstance(value, str):
            self._raw = value.encode("utf-8")
        elif isinstance(value, bytes):
            self._raw = bytes(value)
        else:
            raise TypeError("SecretValue only supports str or bytes")

    def as_bytes(self) -> bytes:
        return bytes(self._raw)

    def as_str(self) -> str:
        return self._raw.decode("utf-8")

    def __repr__(self) -> str:
        return "<SecretValue redacted>"


class SecretsBackend(Protocol):
    backend_name: str

    def set(self, key: SecretKey, value: SecretValue, *, overwrite: bool = False) -> None:
        ...

    def get(self, key: SecretKey) -> SecretValue | None:
        ...

    def delete(self, key: SecretKey) -> None:
        ...

    def list(self, prefix: str | None = None) -> list[SecretKey]:
        ...

    def is_available(self) -> bool:
        ...

    def is_initialized(self) -> bool:
        ...

    def init(self, **kwargs: object) -> None:
        ...

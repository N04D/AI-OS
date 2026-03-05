from __future__ import annotations

import json
from typing import Any

from ..types import BackendUnavailable
from ..types import InvalidKey
from ..types import SecretKey
from ..types import SecretValue


_INDEX_ENTRY = "__aios_index__"


class KeyringBackend:
    backend_name = "keyring"

    def __init__(self, *, service_name: str = "aios", keyring_module: Any | None = None) -> None:
        self.service_name = service_name
        self._keyring = keyring_module
        self._errors: tuple[type[Exception], ...] = (Exception,)
        if self._keyring is None:
            try:
                import keyring  # type: ignore
                from keyring import errors as keyring_errors  # type: ignore
            except Exception as exc:  # pragma: no cover - import environment dependent
                raise BackendUnavailable(
                    "Keyring backend unavailable. Install 'keyring' and ensure OS keychain is running."
                ) from exc
            self._keyring = keyring
            self._errors = (keyring_errors.KeyringError, RuntimeError)

    def _username(self, key: SecretKey | str) -> str:
        if isinstance(key, SecretKey):
            return key.as_str()
        return str(key)

    def _safe_get(self, username: str) -> str | None:
        try:
            return self._keyring.get_password(self.service_name, username)
        except self._errors as exc:
            raise BackendUnavailable(
                "OS keyring is unavailable or locked. Unlock your keychain/login session and retry."
            ) from exc

    def _safe_set(self, username: str, value: str) -> None:
        try:
            self._keyring.set_password(self.service_name, username, value)
        except self._errors as exc:
            raise BackendUnavailable(
                "Failed writing to OS keyring. Verify backend permissions and unlock keychain."
            ) from exc

    def _safe_delete(self, username: str) -> None:
        try:
            self._keyring.delete_password(self.service_name, username)
        except self._errors:
            return

    def _load_index(self) -> set[str]:
        raw = self._safe_get(_INDEX_ENTRY)
        if not raw:
            return set()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return set()
        if not isinstance(parsed, list):
            return set()
        return {str(item) for item in parsed}

    def _save_index(self, values: set[str]) -> None:
        self._safe_set(_INDEX_ENTRY, json.dumps(sorted(values), separators=(",", ":")))

    def is_available(self) -> bool:
        try:
            backend = self._keyring.get_keyring()
            backend_name = backend.__class__.__name__.lower()
            return "fail" not in backend_name
        except Exception:
            return False

    def is_initialized(self) -> bool:
        return self.is_available()

    def init(self, **kwargs: object) -> None:
        del kwargs
        if not self.is_available():
            raise BackendUnavailable(
                "No recommended keyring backend found. Configure SecretService/Keychain/Credential Manager."
            )

    def set(self, key: SecretKey, value: SecretValue, *, overwrite: bool = False) -> None:
        username = self._username(key)
        if not overwrite and self._safe_get(username) is not None:
            raise InvalidKey(f"Secret '{username}' already exists; use overwrite=True")
        self._safe_set(username, value.as_str())
        idx = self._load_index()
        idx.add(username)
        self._save_index(idx)

    def get(self, key: SecretKey) -> SecretValue | None:
        value = self._safe_get(self._username(key))
        if value is None:
            return None
        return SecretValue(value)

    def delete(self, key: SecretKey) -> None:
        username = self._username(key)
        self._safe_delete(username)
        idx = self._load_index()
        idx.discard(username)
        self._save_index(idx)

    def list(self, prefix: str | None = None) -> list[SecretKey]:
        idx = sorted(self._load_index())
        out: list[SecretKey] = []
        for raw in idx:
            if prefix and not raw.startswith(prefix):
                continue
            try:
                out.append(SecretKey.parse(raw))
            except InvalidKey:
                continue
        return out

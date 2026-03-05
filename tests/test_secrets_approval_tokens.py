from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
from aios.secrets.types import AccessDenied
from aios.secrets.types import SecretKey
from aios.secrets.types import SecretValue


class _UnavailableKeyring:
    backend_name = "keyring"

    def is_available(self) -> bool:
        return False

    def is_initialized(self) -> bool:
        return False

    def init(self, **kwargs: object) -> None:
        raise RuntimeError("unavailable")

    def set(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("unavailable")

    def get(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("unavailable")

    def delete(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("unavailable")

    def list(self, *args: object, **kwargs: object) -> list[SecretKey]:
        return []


def _manager(tmp_path: Path) -> SecretsManager:
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    manager = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
    )
    manager.init_fallback("pw")
    return manager


def _approval_token(*, scope: str, exp: int, jti: str) -> str:
    return json.dumps({"v": 1, "scope": [scope], "exp": exp, "jti": jti}, sort_keys=True)


def test_missing_token_denies_critical_secret(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    key = SecretKey.parse("openai.critical_api_key")
    manager.set(key, SecretValue("critical-secret"), overwrite=True)

    with pytest.raises(AccessDenied):
        manager.get(key, context=ContextFactory.interactive_cli())


def test_valid_token_allows_critical_secret(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    key = SecretKey.parse("openai.critical_api_key")
    manager.set(key, SecretValue("critical-secret"), overwrite=True)

    token = _approval_token(
        scope="critical_secret_access",
        exp=int(time.time()) + 600,
        jti="critical-jti-001",
    )
    ctx = ContextFactory.interactive_cli(approval_token=token)
    value = manager.get(key, context=ctx)
    assert value is not None
    assert value.as_str() == "critical-secret"

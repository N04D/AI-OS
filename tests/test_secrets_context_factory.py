from __future__ import annotations

from pathlib import Path

import pytest

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.context import SecretAccessContext
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
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
    )
    mgr.init_fallback("pw")
    mgr.set_fallback_passphrase("pw")
    return mgr


def test_unknown_context_is_denied(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("abc"), overwrite=True)

    with pytest.raises(AccessDenied):
        mgr.get(key, context=SecretAccessContext(context_id="unknown.context", trust_level="standard", elevated=False))


def test_context_argument_is_required(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("abc"), overwrite=True)

    with pytest.raises(TypeError):
        mgr.get(key)  # type: ignore[call-arg]


def test_trust_level_validation_denies_invalid_context_shape(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("abc"), overwrite=True)

    with pytest.raises(AccessDenied):
        mgr.get(key, context=SecretAccessContext(context_id="interactive_cli", trust_level="invalid", elevated=False))


def test_elevated_context_allows_supervisor_token_access(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    key = SecretKey.parse("gitea.token")
    mgr.set(key, SecretValue("token-123"), overwrite=True)

    value = mgr.get(key, context=ContextFactory.supervisor_cli_night_run())
    assert value is not None
    assert value.as_str() == "token-123"

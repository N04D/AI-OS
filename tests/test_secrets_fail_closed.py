from __future__ import annotations

from pathlib import Path

import pytest

from aios.secrets.context import ContextFactory
from aios.secrets.context import SecretAccessContext
from aios.secrets.manager import SecretsManager
from aios.secrets.types import AccessDenied
from aios.secrets.types import BackendUnavailable
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


def test_fail_closed_without_available_or_initialized_backend(tmp_path: Path) -> None:
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_UnavailableKeyring())
    key = SecretKey.parse("openai.api_key")

    with pytest.raises(BackendUnavailable):
        mgr.set(key, SecretValue("x"), overwrite=True)
    with pytest.raises(BackendUnavailable):
        _ = mgr.get(key, context=ContextFactory.interactive_cli())
    with pytest.raises(BackendUnavailable):
        mgr.delete(key)
    with pytest.raises(BackendUnavailable):
        _ = mgr.list()


def test_get_requires_explicit_authorized_context(tmp_path: Path) -> None:
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_UnavailableKeyring())
    mgr.init_fallback("pw")
    mgr.set_fallback_passphrase("pw")
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("abc123secret"), overwrite=True)

    with pytest.raises(AccessDenied):
        _ = mgr.get(
            key,
            context=SecretAccessContext(context_id="unauthorized_context", trust_level="standard", elevated=False),
        )

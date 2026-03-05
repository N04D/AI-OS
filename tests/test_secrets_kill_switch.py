from __future__ import annotations

from pathlib import Path

import pytest

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
from aios.secrets.rate_limits import FixedWindowRateLimiter
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


class _Time:
    def __init__(self, value: float) -> None:
        self.value = value

    def now(self) -> float:
        return self.value


def _manager(
    tmp_path: Path,
    limiter: FixedWindowRateLimiter | None = None,
    *,
    auto_suspend_on_anomaly: bool = False,
) -> SecretsManager:
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
        rate_limiter=limiter,
        auto_suspend_on_anomaly=auto_suspend_on_anomaly,
    )
    mgr.init_fallback("pw")
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("kill-switch-secret"), overwrite=True)
    return mgr


def test_manual_suspend_and_unlock(tmp_path: Path) -> None:
    mgr = _manager(tmp_path)
    key = SecretKey.parse("openai.api_key")
    ctx = ContextFactory.interactive_cli()

    assert mgr.get(key, context=ctx) is not None
    mgr.suspend_context(ctx.context_id)
    with pytest.raises(AccessDenied):
        mgr.get(key, context=ctx)

    mgr.unlock_context(ctx.context_id)
    assert mgr.get(key, context=ctx) is not None


def test_anomaly_triggered_suspension(tmp_path: Path) -> None:
    t = _Time(4_000.0)
    limiter = FixedWindowRateLimiter(
        window_seconds=60,
        limits_by_classification={"standard": 1, "elevated": 1, "low": 1},
        anomaly_multiplier=1.0,
        time_source=t.now,
    )
    mgr = _manager(tmp_path, limiter=limiter, auto_suspend_on_anomaly=True)
    key = SecretKey.parse("openai.api_key")
    ctx = ContextFactory.interactive_cli()

    assert mgr.get(key, context=ctx) is not None
    with pytest.raises(AccessDenied):
        mgr.get(key, context=ctx)

    t.value = 4_061.0
    with pytest.raises(AccessDenied):
        mgr.get(key, context=ctx)
    assert ctx.context_id in mgr.suspended_contexts()

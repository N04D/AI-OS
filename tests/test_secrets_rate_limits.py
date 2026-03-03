from __future__ import annotations

import json
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


def _manager(tmp_path: Path, limiter: FixedWindowRateLimiter) -> SecretsManager:
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
        rate_limiter=limiter,
    )
    mgr.init_fallback("pw")
    mgr.set_fallback_passphrase("pw")
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("secret-token-value"), overwrite=True)
    return mgr


def test_limit_exceed_denies_access(tmp_path: Path) -> None:
    t = _Time(1_000.0)
    limiter = FixedWindowRateLimiter(
        window_seconds=60,
        limits_by_classification={"standard": 2, "elevated": 2, "low": 2},
        time_source=t.now,
    )
    mgr = _manager(tmp_path, limiter)
    key = SecretKey.parse("openai.api_key")
    context = ContextFactory.interactive_cli()

    assert mgr.get(key, context=context) is not None
    assert mgr.get(key, context=context) is not None
    with pytest.raises(AccessDenied):
        mgr.get(key, context=context)


def test_window_reset_allows_after_next_window(tmp_path: Path) -> None:
    t = _Time(2_000.0)
    limiter = FixedWindowRateLimiter(
        window_seconds=60,
        limits_by_classification={"standard": 1, "elevated": 1, "low": 1},
        time_source=t.now,
    )
    mgr = _manager(tmp_path, limiter)
    key = SecretKey.parse("openai.api_key")
    context = ContextFactory.interactive_cli()

    assert mgr.get(key, context=context) is not None
    with pytest.raises(AccessDenied):
        mgr.get(key, context=context)

    t.value = 2_061.0
    assert mgr.get(key, context=context) is not None


def test_anomaly_spike_emits_signal(tmp_path: Path) -> None:
    t = _Time(3_000.0)
    limiter = FixedWindowRateLimiter(
        window_seconds=60,
        limits_by_classification={"standard": 1, "elevated": 1, "low": 1},
        anomaly_multiplier=1.0,
        time_source=t.now,
    )
    mgr = _manager(tmp_path, limiter)
    key = SecretKey.parse("openai.api_key")
    context = ContextFactory.interactive_cli()

    assert mgr.get(key, context=context) is not None
    with pytest.raises(AccessDenied):
        mgr.get(key, context=context)

    audit_path = tmp_path / "audit.jsonl"
    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    error_codes = [line.get("error_code") for line in lines]
    assert "RATE_LIMIT_EXCEEDED" in error_codes
    assert "ANOMALY_SPIKE_DETECTED" in error_codes

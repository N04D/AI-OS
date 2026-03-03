from __future__ import annotations

from pathlib import Path

import pytest

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.budget_gate import BudgetGate
from aios.secrets.budget_sink import BudgetChargeSink
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
    sink = BudgetChargeSink(path=tmp_path / "budget_events.jsonl")
    gate = BudgetGate(
        mode="enforce",
        sink=sink,
        limits_by_classification={"low": 1, "standard": 2, "elevated": 2},
    )
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    manager = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
        budget_mode="enforce",
        budget_sink=sink,
        budget_gate=gate,
    )
    manager.init_fallback("pw")
    key = SecretKey.parse("openai.api_key")
    manager.set(key, SecretValue("quota-value"), overwrite=True)
    return manager


def test_quota_exceed_per_agent_epoch(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    key = SecretKey.parse("openai.api_key")
    context = ContextFactory.interactive_cli(agent_id="agent-A", epoch_id="2026-03-03")

    assert manager.get(key, context=context) is not None
    with pytest.raises(AccessDenied):
        manager.get(key, context=context)


def test_quota_isolation_between_agents(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    key = SecretKey.parse("openai.api_key")

    ctx_a = ContextFactory.interactive_cli(agent_id="agent-A", epoch_id="2026-03-03")
    ctx_b = ContextFactory.interactive_cli(agent_id="agent-B", epoch_id="2026-03-03")

    assert manager.get(key, context=ctx_a) is not None
    assert manager.get(key, context=ctx_b) is not None

    with pytest.raises(AccessDenied):
        manager.get(key, context=ctx_a)

    with pytest.raises(AccessDenied):
        manager.get(key, context=ctx_b)

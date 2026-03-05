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


def test_budget_enforcement_mode_denies_with_budget_exceeded(tmp_path: Path) -> None:
    sink = BudgetChargeSink(path=tmp_path / "budget_events.jsonl")
    gate = BudgetGate(
        mode="enforce",
        sink=sink,
        limits_by_classification={"low": 1, "standard": 2, "elevated": 2},
    )
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
        budget_mode="enforce",
        budget_sink=sink,
        budget_gate=gate,
    )
    mgr.init_fallback("pw")
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue("token123"), overwrite=True)

    assert mgr.get(key, context=ContextFactory.interactive_cli()) is not None
    with pytest.raises(AccessDenied):
        mgr.get(key, context=ContextFactory.interactive_cli())

    audit = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "BUDGET_EXCEEDED" in audit

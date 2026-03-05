from __future__ import annotations

import json
from pathlib import Path

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
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


def test_budget_charge_telemetry_in_observe_mode(tmp_path: Path) -> None:
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    manager = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
        observe_budget_charges=True,
    )
    manager.init_fallback("pw")

    key = SecretKey.parse("openai.api_key")
    manager.set(key, SecretValue("observe-mode-secret"), overwrite=True)
    value = manager.get(key, context=ContextFactory.interactive_cli())
    assert value is not None

    path = tmp_path / "budget_events.jsonl"
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    event = lines[0]
    assert event["event_type"] == "secret.budget.charge"
    assert event["classification"] == "standard"
    assert event["cost"] == 2
    assert event["key"] == "openai.api_key"

    # Telemetry must never leak secret values.
    blob = path.read_text(encoding="utf-8")
    assert "observe-mode-secret" not in blob

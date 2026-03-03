from __future__ import annotations

import hashlib
from pathlib import Path

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
from aios.secrets.types import SecretKey
from aios.secrets.types import SecretValue


FROZEN_SECRETS_EVENTS_V1_SHA256 = "1cd72ff8065b6a423653cece76fd7ba16df1df60102dc3a0e706561e2b3a8a1a"


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


def test_no_secret_values_appear_in_log_files(tmp_path: Path) -> None:
    secret = "final-verify-secret-9001"
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    manager = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
        budget_mode="observe",
    )
    manager.init_fallback("pw")

    key = SecretKey.parse("openai.api_key")
    manager.set(key, SecretValue(secret), overwrite=True)
    value = manager.get(key, context=ContextFactory.interactive_cli())
    assert value is not None

    for path in (tmp_path / "audit.jsonl", tmp_path / "budget_events.jsonl"):
        content = path.read_text(encoding="utf-8")
        assert secret not in content


def test_store_v1_readable_roundtrip(tmp_path: Path) -> None:
    store = tmp_path / "store.v1"
    backend = EncryptedStoreBackend(store_path=store)
    key = SecretKey.parse("gitea.token")

    backend.init(passphrase="pw")
    backend.set(key, SecretValue("readable-value"), overwrite=True, passphrase="pw")

    loaded = backend.get(key, passphrase="pw")
    assert loaded is not None
    assert loaded.as_str() == "readable-value"


def test_event_schema_unchanged_sha256() -> None:
    schema_path = Path("docs/specs/secrets_events.v1.json")
    digest = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    assert digest == FROZEN_SECRETS_EVENTS_V1_SHA256

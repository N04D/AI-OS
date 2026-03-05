from __future__ import annotations

import json
from pathlib import Path
import threading

import pytest

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.hardening import disable_core_dumps_best_effort
from aios.secrets.manager import SecretsManager
from aios.secrets.types import SecretKey
from aios.secrets.types import SecretValue
from aios.secrets.types import SecretsError


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


def test_secret_value_wipe_and_context_manager() -> None:
    value = SecretValue("hardening-secret")
    assert value.as_str() == "hardening-secret"
    value.wipe()
    with pytest.raises(SecretsError):
        value.as_str()

    with SecretValue("another-secret") as scoped:
        assert scoped.as_str() == "another-secret"
    with pytest.raises(SecretsError):
        scoped.as_bytes()


def test_no_log_leak_for_secret_material(tmp_path: Path) -> None:
    secret = "log-leak-check-4455"
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
    )
    mgr.init_fallback("pw")
    key = SecretKey.parse("openai.api_key")
    mgr.set(key, SecretValue(secret), overwrite=True)
    _ = mgr.get(key, context=ContextFactory.interactive_cli())

    audit_path = tmp_path / "audit.jsonl"
    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    for event in lines:
        encoded = json.dumps(event, sort_keys=True)
        assert secret not in encoded


def test_concurrent_writes_keep_store_readable(tmp_path: Path) -> None:
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    key = SecretKey.parse("openai.api_key")
    backend.init(passphrase="pw")

    errors: list[Exception] = []

    def _writer(idx: int) -> None:
        try:
            backend.set(key, SecretValue(f"value-{idx}"), overwrite=True, passphrase="pw")
        except Exception as exc:  # pragma: no cover - test assertion handles
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    loaded = backend.get(key, passphrase="pw")
    assert loaded is not None
    assert loaded.as_str().startswith("value-")


def test_optional_core_dump_disable_is_best_effort() -> None:
    assert disable_core_dumps_best_effort() in {True, False}

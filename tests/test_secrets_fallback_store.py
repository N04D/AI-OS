from __future__ import annotations

from pathlib import Path

import pytest

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.types import SecretKey
from aios.secrets.types import SecretValue


def test_fallback_store_roundtrip_and_rotation(tmp_path: Path) -> None:
    store = tmp_path / "store.v1"
    backend = EncryptedStoreBackend(store_path=store)
    key = SecretKey.parse("gitea.token")

    backend.init(passphrase="old-passphrase")
    backend.set(key, SecretValue("token-value-123"), passphrase="old-passphrase", overwrite=False)

    loaded = backend.get(key, passphrase="old-passphrase")
    assert loaded is not None
    assert loaded.as_str() == "token-value-123"

    backend.rotate_passphrase("old-passphrase", "new-passphrase")
    rotated = backend.get(key, passphrase="new-passphrase")
    assert rotated is not None
    assert rotated.as_str() == "token-value-123"


def test_fallback_atomic_write_keeps_old_file_on_replace_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "store.v1"
    backend = EncryptedStoreBackend(store_path=store)
    key = SecretKey.parse("openai.api_key")

    backend.init(passphrase="pw")
    backend.set(key, SecretValue("first-secret-value"), passphrase="pw", overwrite=True)
    before = store.read_bytes()

    def _boom(src: str, dst: str) -> None:
        raise OSError("simulated crash before rename")

    monkeypatch.setattr("aios.secrets.backends.encrypted_store_backend.os.replace", _boom)
    with pytest.raises(OSError):
        backend.set(key, SecretValue("second-secret-value"), passphrase="pw", overwrite=True)

    assert store.read_bytes() == before
    still = backend.get(key, passphrase="pw")
    assert still is not None
    assert still.as_str() == "first-secret-value"

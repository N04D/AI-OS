from __future__ import annotations

from pathlib import Path

from aios.secrets.manager import SecretsManager
from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.redaction import redact
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


def test_redaction_and_no_plaintext_in_audit_or_store(tmp_path: Path) -> None:
    secret = "super-sensitive-value-987"
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
    )
    mgr.init_fallback("pw")

    key = SecretKey.parse("openai.api_key")
    wrapped = SecretValue(secret)
    assert repr(wrapped) == "<SecretValue redacted>"
    assert redact(secret).startswith("sup***")

    mgr.set(key, wrapped, overwrite=True)
    _ = mgr.get(key, context=ContextFactory.interactive_cli())

    for path in tmp_path.rglob("*"):
        if path.is_file():
            text = path.read_bytes()
            assert secret.encode("utf-8") not in text

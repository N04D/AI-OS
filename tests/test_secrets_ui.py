from __future__ import annotations

import re
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from aios.secrets.backends.encrypted_store_backend import EncryptedStoreBackend
from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
from aios.secrets.types import SecretKey
from aios.secrets.ui.routes import create_app


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


def test_secrets_ui_save_does_not_echo_or_store_plaintext(tmp_path: Path) -> None:
    secret = "ui-secret-value-445566"
    backend = EncryptedStoreBackend(store_path=tmp_path / "store.v1")
    mgr = SecretsManager(
        data_dir=tmp_path,
        keyring_backend=_UnavailableKeyring(),
        fallback_backend=backend,
        fallback_passphrase="pw",
    )
    mgr.init_fallback("pw")
    app = create_app(manager=mgr)

    client = TestClient(app)
    get_resp = client.get("/settings/secrets")
    assert get_resp.status_code == 200
    assert 'type="password"' in get_resp.text

    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "openai.api_key", "value": secret, "action": "save"},
    )
    assert post_resp.status_code == 200
    assert "Saved." in post_resp.text
    assert secret not in post_resp.text

    loaded = mgr.get(SecretKey.parse("openai.api_key"), context=ContextFactory.interactive_cli())
    assert loaded is not None
    assert loaded.as_str() == secret

    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert secret.encode("utf-8") not in path.read_bytes()

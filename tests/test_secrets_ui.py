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
from aios.secrets.types import SecretValue
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


class _InMemoryKeyring:
    backend_name = "keyring"

    def __init__(self) -> None:
        self._store: dict[str, SecretValue] = {}

    def is_available(self) -> bool:
        return True

    def is_initialized(self) -> bool:
        return True

    def init(self, **kwargs: object) -> None:
        del kwargs

    def set(self, key: SecretKey, value: SecretValue, *, overwrite: bool = False) -> None:
        if not overwrite and key.as_str() in self._store:
            raise RuntimeError("exists")
        self._store[key.as_str()] = SecretValue(value.as_str())

    def get(self, key: SecretKey) -> SecretValue | None:
        found = self._store.get(key.as_str())
        if found is None:
            return None
        return SecretValue(found.as_str())

    def delete(self, key: SecretKey) -> None:
        self._store.pop(key.as_str(), None)

    def list(self, *args: object, **kwargs: object) -> list[SecretKey]:
        del args, kwargs
        return [SecretKey.parse(raw) for raw in sorted(self._store)]


def test_secrets_ui_save_requires_keyring_and_does_not_fallback(tmp_path: Path) -> None:
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
    assert 'name="action" value="save" disabled' in get_resp.text

    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "openai.api_key", "value": secret, "action": "save"},
    )
    assert post_resp.status_code == 503
    assert "keyring-only" in post_resp.text
    assert secret not in post_resp.text

    loaded = mgr.get(SecretKey.parse("openai.api_key"), context=ContextFactory.interactive_cli())
    assert loaded is None

    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert secret.encode("utf-8") not in path.read_bytes()


def test_secrets_ui_save_stores_value_when_keyring_available(tmp_path: Path) -> None:
    secret = "ui-secret-value-998877"
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_InMemoryKeyring())
    app = create_app(manager=mgr)

    client = TestClient(app)
    get_resp = client.get("/settings/secrets")
    assert get_resp.status_code == 200
    assert "Backend:" in get_resp.text
    assert "Test uses saved key when empty." in get_resp.text
    assert "Gitea SSH Private Key" in get_resp.text
    assert "Email SMTP Password" in get_resp.text
    assert "GitHub Personal Token" in get_resp.text
    assert "GitHub Work Token" in get_resp.text

    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "openai.api_key", "value": secret, "action": "save"},
    )
    assert post_resp.status_code == 200
    assert "Saved to OS keyring." in post_resp.text
    assert secret not in post_resp.text

    loaded = mgr.get(SecretKey.parse("openai.api_key"), context=ContextFactory.interactive_cli())
    assert loaded is not None
    assert loaded.as_str() == secret


def test_secrets_ui_save_trims_whitespace(tmp_path: Path) -> None:
    secret = "ui-secret-value-trim-1234"
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_InMemoryKeyring())
    app = create_app(manager=mgr)

    client = TestClient(app)
    get_resp = client.get("/settings/secrets")
    assert get_resp.status_code == 200

    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "openai.api_key", "value": f"  {secret}\n", "action": "save"},
    )
    assert post_resp.status_code == 200

    loaded = mgr.get(SecretKey.parse("openai.api_key"), context=ContextFactory.interactive_cli())
    assert loaded is not None
    assert loaded.as_str() == secret


def test_secrets_ui_test_connection_uses_saved_key_when_input_empty(tmp_path: Path) -> None:
    secret = "sk-ui-secret-value-for-test-778899"
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_InMemoryKeyring())
    mgr.set(SecretKey.parse("openai.api_key"), SecretValue(secret), overwrite=True)
    app = create_app(manager=mgr)

    client = TestClient(app)
    get_resp = client.get("/settings/secrets")
    assert get_resp.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "openai.api_key", "value": "", "action": "test"},
    )
    assert post_resp.status_code == 200
    assert "OpenAI key format looks valid." in post_resp.text


def test_secrets_ui_test_connection_requires_value_or_saved_key(tmp_path: Path) -> None:
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_InMemoryKeyring())
    app = create_app(manager=mgr)

    client = TestClient(app)
    get_resp = client.get("/settings/secrets")
    assert get_resp.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "openai.api_key", "value": "", "action": "test"},
    )
    assert post_resp.status_code == 400
    assert "No key available to test." in post_resp.text


def test_secrets_ui_save_multiline_ssh_key(tmp_path: Path) -> None:
    ssh_key = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc123\n-----END OPENSSH PRIVATE KEY-----\n"
    mgr = SecretsManager(data_dir=tmp_path, keyring_backend=_InMemoryKeyring())
    app = create_app(manager=mgr)

    client = TestClient(app)
    get_resp = client.get("/settings/secrets")
    assert get_resp.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', get_resp.text)
    assert match is not None
    token = match.group(1)

    post_resp = client.post(
        "/settings/secrets",
        data={"csrf_token": token, "key": "gitea.ssh_private_key", "secret_value": ssh_key, "action": "save"},
    )
    assert post_resp.status_code == 200
    assert "Saved to OS keyring." in post_resp.text

    loaded = mgr.get(SecretKey.parse("gitea.ssh_private_key"), context=ContextFactory.interactive_cli())
    assert loaded is not None
    assert loaded.as_str().startswith("-----BEGIN OPENSSH PRIVATE KEY-----")

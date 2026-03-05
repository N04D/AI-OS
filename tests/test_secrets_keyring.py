from __future__ import annotations

from dataclasses import dataclass

from aios.secrets.backends.keyring_backend import KeyringBackend
from aios.secrets.types import SecretKey
from aios.secrets.types import SecretValue


class _DummyBackend:
    pass


@dataclass
class _FakeKeyring:
    store: dict[tuple[str, str], str]

    def get_keyring(self) -> object:
        return _DummyBackend()

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, value: str) -> None:
        self.store[(service, username)] = value

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


def test_keyring_backend_roundtrip() -> None:
    backend = KeyringBackend(service_name="aios", keyring_module=_FakeKeyring(store={}))
    key = SecretKey.parse("openai.api_key")

    backend.set(key, SecretValue("sk-test-123456"), overwrite=False)
    got = backend.get(key)
    assert got is not None
    assert got.as_str() == "sk-test-123456"

    listed = [k.as_str() for k in backend.list()]
    assert "openai.api_key" in listed

    backend.delete(key)
    assert backend.get(key) is None

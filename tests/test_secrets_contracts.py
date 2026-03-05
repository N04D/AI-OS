from __future__ import annotations

from aios.secrets.backends.encrypted_store_backend import MAGIC
from aios.secrets.contracts import SECRETS_EVENT_SCHEMA_VERSION
from aios.secrets.contracts import STORE_FORMAT_MAGIC


def test_event_schema_version_constant() -> None:
    assert SECRETS_EVENT_SCHEMA_VERSION == "secrets_events.v1"


def test_store_header_magic_constant() -> None:
    assert MAGIC == b"AIOSSEC1"
    assert STORE_FORMAT_MAGIC == b"AIOSSEC1"

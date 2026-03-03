from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any
from typing import Protocol

from .contracts import SECRETS_EVENT_SCHEMA_PATH
from .contracts import SECRETS_EVENT_SCHEMA_VERSION
from .types import SecretsError


class EventBusEmitFailed(SecretsError):
    """Raised when event emission fails."""

    reason_code = "EVENTBUS_EMIT_FAILED"


class EventSink(Protocol):
    def emit(self, event: dict[str, Any]) -> None:
        ...


@dataclass(frozen=True)
class SecretsEventSchemaValidator:
    schema_path: Path

    @classmethod
    def default(cls) -> "SecretsEventSchemaValidator":
        root = Path(__file__).resolve().parents[2]
        return cls(schema_path=root / SECRETS_EVENT_SCHEMA_PATH)

    def _schema(self) -> dict[str, Any]:
        with self.schema_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: invalid_schema")
        return data

    def validate(self, event: dict[str, Any]) -> None:
        schema = self._schema()
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: malformed_schema")

        missing = [name for name in required if name not in event]
        if missing:
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: missing_required_fields")

        if schema.get("additionalProperties") is False:
            unknown = set(event.keys()) - set(properties.keys())
            if unknown:
                raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: unknown_fields")

        if str(event.get("schema_version", "")) != SECRETS_EVENT_SCHEMA_VERSION:
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: schema_version_mismatch")

        for key, value in event.items():
            rules = properties.get(key)
            if not isinstance(rules, dict):
                continue
            allowed = rules.get("type")
            if isinstance(allowed, list):
                if value is None and "null" not in allowed:
                    raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: type_check_failed")
                if value is not None and "string" in allowed and not isinstance(value, str):
                    raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: type_check_failed")
            elif allowed == "string" and not isinstance(value, str):
                raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: type_check_failed")

            enum = rules.get("enum")
            if isinstance(enum, list) and value not in enum:
                raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: enum_check_failed")

            const = rules.get("const")
            if const is not None and value != const:
                raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: const_check_failed")

            max_length = rules.get("maxLength")
            if isinstance(max_length, int) and isinstance(value, str) and len(value) > max_length:
                raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: max_length_failed")

        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str):
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: timestamp_type_invalid")
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: timestamp_format_invalid") from exc


@dataclass
class SupervisorEventSink:
    path: Path
    validator: SecretsEventSchemaValidator | None = None

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        os.chmod(self.path, 0o600)
        if self.validator is None:
            self.validator = SecretsEventSchemaValidator.default()

    def emit(self, event: dict[str, Any]) -> None:
        try:
            assert self.validator is not None
            self.validator.validate(event)
            line = json.dumps(event, sort_keys=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception as exc:
            if isinstance(exc, EventBusEmitFailed):
                raise
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: supervisor_file_sink") from exc


@dataclass
class MultiplexerSink:
    sinks: list[EventSink]

    def emit(self, event: dict[str, Any]) -> None:
        failures: list[Exception] = []
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception as exc:
                failures.append(exc)
        if failures:
            raise EventBusEmitFailed("EVENTBUS_EMIT_FAILED: multiplexer") from failures[0]

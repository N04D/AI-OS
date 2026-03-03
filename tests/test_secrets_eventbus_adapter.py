from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios.secrets.contracts import SECRETS_EVENT_SCHEMA_VERSION
from aios.secrets.eventbus import EventBusEmitFailed
from aios.secrets.eventbus import EventSink
from aios.secrets.eventbus import MultiplexerSink
from aios.secrets.eventbus import SupervisorEventSink


def _valid_event() -> dict[str, object]:
    return {
        "schema_version": SECRETS_EVENT_SCHEMA_VERSION,
        "timestamp": "2026-03-03T00:00:00+00:00",
        "user": "tester",
        "action": "set",
        "key": "openai.api_key",
        "backend": "keyring",
        "result": "ok",
        "error_code": None,
    }


class _CaptureSink:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, event: dict[str, object]) -> None:
        self.events.append(dict(event))


class _FailingSink:
    def emit(self, event: dict[str, object]) -> None:
        del event
        raise RuntimeError("boom")


def test_multiplexer_fanout_emits_to_all_sinks() -> None:
    a = _CaptureSink()
    b = _CaptureSink()
    sink: EventSink = MultiplexerSink([a, b])

    event = _valid_event()
    sink.emit(event)

    assert a.events == [event]
    assert b.events == [event]


def test_supervisor_sink_validates_against_schema_and_writes_file(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = SupervisorEventSink(path=path)

    sink.emit(_valid_event())

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["schema_version"] == SECRETS_EVENT_SCHEMA_VERSION
    assert payload["action"] == "set"


def test_failure_handling_raises_eventbus_emit_failed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = SupervisorEventSink(path=path)
    bad = _valid_event()
    bad["schema_version"] = "wrong-version"

    with pytest.raises(EventBusEmitFailed) as exc:
        sink.emit(bad)
    assert "EVENTBUS_EMIT_FAILED" in str(exc.value)


def test_multiplexer_surfaces_eventbus_emit_failed() -> None:
    good = _CaptureSink()
    sink = MultiplexerSink([good, _FailingSink()])

    with pytest.raises(EventBusEmitFailed) as exc:
        sink.emit(_valid_event())
    assert "EVENTBUS_EMIT_FAILED" in str(exc.value)
    assert len(good.events) == 1

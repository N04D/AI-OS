from __future__ import annotations

import json
from pathlib import Path

from kernel.channels.email import EVENT_TYPE
from kernel.channels.email import emit_email_artifact
from kernel.channels.email import parse_inbox_artifact


def test_parse_inbox_artifact_requires_subject_or_body(tmp_path: Path) -> None:
    path = tmp_path / "inbox.json"
    path.write_text(json.dumps({"from": "a@example.com"}, sort_keys=True), encoding="utf-8")
    try:
        parse_inbox_artifact(path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "subject or body" in str(exc)


def test_emit_email_artifact_emits_channel_event(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    artifact = tmp_path / "mail.json"
    artifact.write_text(
        json.dumps(
            {
                "agent": "codex",
                "from": "don.berghuijs@gmail.com",
                "to": "nova69.agent@gmail.com",
                "subject": "AI-OS Ping",
                "body": "check this",
                "uid": "101",
                "epoch": "epoch-abc",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_emit(
        event_type: str,
        payload: dict,
        *,
        registry_path: str,
        config_path: str,
        audit_log_path: str,
    ) -> dict:
        captured["event_type"] = event_type
        captured["payload"] = payload
        captured["registry_path"] = registry_path
        captured["config_path"] = config_path
        captured["audit_log_path"] = audit_log_path
        return {"ok": True, "event_id": "evt-1", "event_type": event_type, "delivered": [], "failed": []}

    monkeypatch.setattr("kernel.channels.email.events.emit", _fake_emit)

    result = emit_email_artifact(
        artifact,
        registry_path="state/plugins/registry.json",
        config_path="state/plugins/config.json",
        audit_log_path="logs/control/kernel-events.jsonl",
    )

    assert result["ok"] is True
    assert captured["event_type"] == EVENT_TYPE
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["channel"] == "email"
    assert payload["subject"] == "AI-OS Ping"
    assert payload["body"] == "check this"

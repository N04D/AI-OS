from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path

from supervisor.skills.email_send import DENY_EMAIL_CAPABILITY_MISSING
from supervisor.skills.email_send import DENY_EMAIL_NETWORK_UNAVAILABLE
from supervisor.skills.email_send import DENY_EMAIL_SECRETS_MISSING
from supervisor.skills.email_send import run_email_send


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def test_email_send_denied_when_capability_missing(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "state" / "capabilities" / "enabled.json"
    audit = tmp_path / "logs" / "control" / "email_send_audit.jsonl"
    _write_json(registry, {"enabled": ["repo_write", "tests_run"]})

    monkeypatch.setenv("NETWORK_ACCESS_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    result = run_email_send(
        {"to": "dev@example.com", "subject": "s", "body": "b"},
        capability_registry_path=registry,
        audit_log_path=audit,
        now_utc=datetime(2026, 2, 28, 0, 0, 0, tzinfo=UTC),
    )

    assert result["ok"] is False
    assert result["reason_code"] == DENY_EMAIL_CAPABILITY_MISSING
    row = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert row["reason_code"] == DENY_EMAIL_CAPABILITY_MISSING


def test_email_send_denied_when_secrets_missing(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "state" / "capabilities" / "enabled.json"
    audit = tmp_path / "logs" / "control" / "email_send_audit.jsonl"
    _write_json(registry, {"enabled": ["email.send"]})

    monkeypatch.setenv("NETWORK_ACCESS_ENABLED", "true")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    result = run_email_send(
        {"to": "dev@example.com", "subject": "s", "body": "b"},
        capability_registry_path=registry,
        audit_log_path=audit,
        now_utc=datetime(2026, 2, 28, 0, 0, 1, tzinfo=UTC),
    )

    assert result["ok"] is False
    assert result["reason_code"] == DENY_EMAIL_SECRETS_MISSING
    assert sorted(result["missing"]) == ["SMTP_FROM", "SMTP_HOST", "SMTP_PASS", "SMTP_PORT", "SMTP_USER"]


def test_email_send_denied_when_network_dependency_missing(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "state" / "capabilities" / "enabled.json"
    audit = tmp_path / "logs" / "control" / "email_send_audit.jsonl"
    _write_json(registry, {"enabled": ["email.send"]})

    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("NETWORK_ACCESS_ENABLED", "false")

    result = run_email_send(
        {"to": "dev@example.com", "subject": "s", "body": "b"},
        capability_registry_path=registry,
        audit_log_path=audit,
        now_utc=datetime(2026, 2, 28, 0, 0, 2, tzinfo=UTC),
    )

    assert result["ok"] is False
    assert result["reason_code"] == DENY_EMAIL_NETWORK_UNAVAILABLE


def test_email_send_allowed_and_audited(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "state" / "capabilities" / "enabled.json"
    audit = tmp_path / "logs" / "control" / "email_send_audit.jsonl"
    _write_json(registry, {"enabled": ["email.send", "repo_write"]})

    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("NETWORK_ACCESS_ENABLED", "true")

    result = run_email_send(
        {"to": "dev@example.com", "subject": "hello", "body": "world"},
        capability_registry_path=registry,
        audit_log_path=audit,
        now_utc=datetime(2026, 2, 28, 0, 0, 3, tzinfo=UTC),
    )

    assert result["ok"] is True
    row = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert row["allowed"] is True
    assert row["transport"] == "smtp"
    assert row["capability"] == "email.send"


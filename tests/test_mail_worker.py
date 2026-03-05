from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = REPO_ROOT / "tools" / "mail_worker.py"


class _OkTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send_mail(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {"status": "sent"}


class _AlwaysTransientFailTransport:
    def send_mail(self, **kwargs: Any) -> dict[str, Any]:
        raise OSError("temporary_failure")


class _FlakyTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send_mail(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls < 3:
            raise OSError("temporary_failure")
        return {"status": "sent"}


def _load_worker_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("mail_worker", WORKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_outbox_message(workspace_root: Path, *, agent: str = "codex", message_id: str = "msg-1") -> Path:
    outbox = workspace_root / agent / "mail" / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": message_id,
        "to": "to@example.com",
        "subject": "Hello",
        "body": "Body",
        "timestamp": "2026-03-03T22:00:00Z",
        "status": "pending",
    }
    path = outbox / f"{message_id}.json"
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def test_worker_success_moves_message_to_sent(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_worker_module()
    workspace_root = tmp_path / "workspace"
    _write_outbox_message(workspace_root, message_id="ok-1")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    transport = _OkTransport()
    worker = module.MailWorker(
        workspace_root=workspace_root,
        transport=transport,
        secret_provider=lambda: "pw",
    )
    summary = worker.run_once(agent="codex")

    assert summary.to_dict() == {"processed": 1, "sent": 1, "failed": 0, "retried": 0}
    assert transport.calls == 1
    assert not (workspace_root / "codex" / "mail" / "outbox" / "ok-1.json").exists()
    sent_path = workspace_root / "codex" / "mail" / "sent" / "ok-1.json"
    assert sent_path.exists()
    sent_payload = json.loads(sent_path.read_text(encoding="utf-8"))
    assert sent_payload["status"] == "sent"
    assert sent_payload["attempts"] == 1


def test_worker_transient_failure_retries_then_moves_to_failed(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_worker_module()
    workspace_root = tmp_path / "workspace"
    _write_outbox_message(workspace_root, message_id="fail-1")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    worker = module.MailWorker(
        workspace_root=workspace_root,
        transport=_AlwaysTransientFailTransport(),
        secret_provider=lambda: "pw",
        max_retries=3,
    )

    first = worker.run_once(agent="codex")
    second = worker.run_once(agent="codex")
    third = worker.run_once(agent="codex")

    assert first.to_dict() == {"processed": 1, "sent": 0, "failed": 0, "retried": 1}
    assert second.to_dict() == {"processed": 1, "sent": 0, "failed": 0, "retried": 1}
    assert third.to_dict() == {"processed": 1, "sent": 0, "failed": 1, "retried": 0}

    assert not (workspace_root / "codex" / "mail" / "outbox" / "fail-1.json").exists()
    failed_path = workspace_root / "codex" / "mail" / "failed" / "fail-1.json"
    assert failed_path.exists()
    failed_payload = json.loads(failed_path.read_text(encoding="utf-8"))
    assert failed_payload["status"] == "failed"
    assert failed_payload["attempts"] == 3
    assert failed_payload["error"] == "OSError"


def test_worker_retry_succeeds_on_third_attempt(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_worker_module()
    workspace_root = tmp_path / "workspace"
    _write_outbox_message(workspace_root, message_id="flaky-1")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    transport = _FlakyTransport()
    worker = module.MailWorker(
        workspace_root=workspace_root,
        transport=transport,
        secret_provider=lambda: "pw",
        max_retries=3,
    )

    worker.run_once(agent="codex")
    worker.run_once(agent="codex")
    summary = worker.run_once(agent="codex")

    assert summary.to_dict() == {"processed": 1, "sent": 1, "failed": 0, "retried": 0}
    assert transport.calls == 3
    assert not (workspace_root / "codex" / "mail" / "outbox" / "flaky-1.json").exists()
    sent_path = workspace_root / "codex" / "mail" / "sent" / "flaky-1.json"
    assert sent_path.exists()
    sent_payload = json.loads(sent_path.read_text(encoding="utf-8"))
    assert sent_payload["status"] == "sent"
    assert sent_payload["attempts"] == 3

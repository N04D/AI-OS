from __future__ import annotations

import importlib.util
import io
import json
import logging
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = REPO_ROOT / "tools" / "mail_worker.py"


class _LeakyErrorTransport:
    def send_mail(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("auth_failed_with_password_SUPER_SECRET_PASS")


def _load_worker_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("mail_worker", WORKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_outbox_message(workspace_root: Path, message_id: str) -> None:
    outbox = workspace_root / "codex" / "mail" / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": message_id,
        "to": "to@example.com",
        "subject": "Hello",
        "body": "Body",
        "timestamp": "2026-03-03T22:00:00Z",
        "status": "pending",
    }
    (outbox / f"{message_id}.json").write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def test_worker_logs_and_files_do_not_leak_smtp_password(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    module = _load_worker_module()
    workspace_root = tmp_path / "workspace"
    _write_outbox_message(workspace_root, "leak-1")

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("mail_worker")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    worker = module.MailWorker(
        workspace_root=workspace_root,
        transport=_LeakyErrorTransport(),
        secret_provider=lambda: "SUPER_SECRET_PASS",
        max_retries=1,
    )
    worker.run_once(agent="codex")

    logs = stream.getvalue()
    assert "SUPER_SECRET_PASS" not in logs

    for path in workspace_root.rglob("*.json"):
        assert "SUPER_SECRET_PASS" not in path.read_text(encoding="utf-8")

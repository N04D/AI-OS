from __future__ import annotations

import json
import os
import stat
import subprocess
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_send_queues_message_without_aiosctl_or_network(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    env = os.environ.copy()
    env["AIOS_MAIL_WORKSPACE_ROOT"] = str(workspace_root)
    env["AIOS_MAIL_QUEUE_NOW"] = "2026-03-03T22:00:00Z"
    env["AIOS_EMAIL_SAFE_RUN_FORBID_AIOSCTL"] = "1"

    proc = subprocess.run(
        [
            "bash",
            "tools/email_safe_run.sh",
            "send",
            "--json",
            "--agent",
            "codex",
            "--to",
            "don.berghuijs@gmail.com",
            "--subject",
            "Vraag",
            "--body",
            "Wat is je eigen e-mailadres?",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["status"] == "queued"
    message_id = payload["id"]
    uuid.UUID(message_id)

    queued = workspace_root / "codex" / "mail" / "outbox" / f"{message_id}.json"
    assert queued.exists()
    mode = stat.S_IMODE(queued.stat().st_mode)
    assert mode == 0o600

    message = json.loads(queued.read_text(encoding="utf-8"))
    assert message == {
        "id": message_id,
        "to": "don.berghuijs@gmail.com",
        "subject": "Vraag",
        "body": "Wat is je eigen e-mailadres?",
        "timestamp": "2026-03-03T22:00:00Z",
        "status": "pending",
    }

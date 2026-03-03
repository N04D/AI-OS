from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path

from supervisor.dispatch_worker import run_dispatch_worker
from supervisor.email_queue import enqueue_morning_dispatch
from supervisor.night_report import write_nightly_report


def test_dispatch_worker_enforces_idempotency_key(tmp_path: Path) -> None:
    report_root = tmp_path / "state/reports/nightly"
    queue_root = tmp_path / "state/email_queue"
    ledger_path = tmp_path / "state/email_ledger.json"
    audit_path = tmp_path / "logs/control/nightly_dispatch_audit.jsonl"

    report = {
        "date": "2026-03-01",
        "epoch": "2026-03-01",
        "summary": "night run complete",
        "tasks_executed": ["t1"],
        "failures": [],
        "budget_used": 1.0,
        "stopped": True,
        "toolchain_hash": "1" * 64,
    }
    report_result = write_nightly_report(report, report_root=report_root, audit_log_path=audit_path)
    queue_result = enqueue_morning_dispatch(
        date="2026-03-01",
        report_path=report_result["report_path"],
        report_hash=report_result["report_hash"],
        operator_utc_offset="+00:00",
        queue_root=queue_root,
        audit_log_path=audit_path,
    )

    now = datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC)
    first = run_dispatch_worker(
        queue_root=queue_root,
        ledger_path=ledger_path,
        audit_log_path=audit_path,
        now_utc=now,
    )
    assert first["sent"] == 1
    assert first["failed"] == 0

    queue_path = Path(queue_result["queue_path"])
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    assert payload["status"] == "sent"

    # Simulate accidental queue replay with same idempotency key.
    payload["status"] = "pending"
    queue_path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    second = run_dispatch_worker(
        queue_root=queue_root,
        ledger_path=ledger_path,
        audit_log_path=audit_path,
        now_utc=now,
    )
    assert second["sent"] == 0
    assert second["failed"] == 1
    replay_payload = json.loads(queue_path.read_text(encoding="utf-8"))
    assert replay_payload["status"] == "failed"

    audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [row["event_type"] for row in audit_rows]
    assert "dispatch_sent" in event_types
    assert "dispatch_failed" in event_types

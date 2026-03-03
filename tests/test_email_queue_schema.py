from __future__ import annotations

import json
from pathlib import Path

import pytest

from supervisor.email_queue import EmailQueueError
from supervisor.email_queue import enqueue_morning_dispatch
from supervisor.email_queue import validate_queue_schema


def test_enqueue_morning_dispatch_writes_valid_queue_item(tmp_path: Path) -> None:
    queue_root = tmp_path / "state/email_queue"
    audit_path = tmp_path / "logs/control/nightly_dispatch_audit.jsonl"
    result = enqueue_morning_dispatch(
        date="2026-03-03",
        report_path="state/reports/nightly/2026-03-03.json",
        report_hash="b" * 64,
        operator_utc_offset="+01:00",
        queue_root=queue_root,
        audit_log_path=audit_path,
    )
    queue_path = Path(result["queue_path"])
    assert queue_path.exists()
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    validate_queue_schema(payload)
    assert payload["scheduled_at_utc"] == "2026-03-03T08:30:00Z"
    assert payload["status"] == "pending"

    audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(audit_rows) == 1
    assert audit_rows[0]["event_type"] == "queue_enqueued"


def test_validate_queue_schema_rejects_invalid_status() -> None:
    payload = {
        "scheduled_at_utc": "2026-03-03T09:30:00Z",
        "idempotency_key": "c" * 64,
        "report_path": "state/reports/nightly/2026-03-03.json",
        "report_hash": "d" * 64,
        "status": "unknown",
    }
    with pytest.raises(EmailQueueError):
        validate_queue_schema(payload)


def test_enqueue_fails_closed_on_existing_conflicting_item(tmp_path: Path) -> None:
    queue_root = tmp_path / "state/email_queue"
    queue_root.mkdir(parents=True, exist_ok=True)
    queue_path = queue_root / "2026-03-03__0930.json"
    queue_path.write_text(
        json.dumps(
            {
                "scheduled_at_utc": "2026-03-03T09:30:00Z",
                "idempotency_key": "e" * 64,
                "report_path": "other/path.json",
                "report_hash": "f" * 64,
                "status": "pending",
            },
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(EmailQueueError):
        enqueue_morning_dispatch(
            date="2026-03-03",
            report_path="state/reports/nightly/2026-03-03.json",
            report_hash="b" * 64,
            operator_utc_offset="+00:00",
            queue_root=queue_root,
            audit_log_path=tmp_path / "logs/control/nightly_dispatch_audit.jsonl",
        )

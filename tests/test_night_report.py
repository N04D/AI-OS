from __future__ import annotations

import json
from pathlib import Path

from supervisor.night_report import write_nightly_report


def test_write_nightly_report_generates_report_hash_and_audit(tmp_path: Path) -> None:
    report_root = tmp_path / "state/reports/nightly"
    audit_path = tmp_path / "logs/control/nightly_dispatch_audit.jsonl"
    payload = {
        "date": "2026-03-03",
        "epoch": "2026-03-03",
        "summary": "Nightly build completed",
        "tasks_executed": ["task_a", "task_b"],
        "failures": [],
        "budget_used": 4.5,
        "stopped": True,
        "toolchain_hash": "a" * 64,
    }

    result = write_nightly_report(payload, report_root=report_root, audit_log_path=audit_path)
    report_path = Path(result["report_path"])
    assert report_path.exists()
    assert report_path.name == "2026-03-03.json"
    sidecar_path = report_root / "2026-03-03.json.sha256"
    assert sidecar_path.exists()
    assert sidecar_path.read_text(encoding="utf-8").strip() == result["report_hash"]

    audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(audit_rows) == 1
    assert audit_rows[0]["event_type"] == "report_generated"
    assert audit_rows[0]["payload"]["report_hash"] == result["report_hash"]

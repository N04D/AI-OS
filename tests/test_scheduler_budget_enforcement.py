from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from supervisor import cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _guarded_job() -> dict:
    return {
        "job_id": "nightly_audit",
        "enabled": True,
        "schedule": {"type": "interval_minutes", "every": 1},
        "event_type": "scheduler.job_due",
        "payload": {"task": "nightly_audit"},
        "mode": "guarded_skill",
    }


def test_guarded_skill_budget_exhaustion_denies_handler_but_still_emits_event(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    budget_path = tmp_path / "state" / "budgets.json"

    _write_json(jobs_path, {"version": "v0.1", "timezone": "UTC", "jobs": [_guarded_job()]})
    _write_json(ledger_path, {"scheduler_guarded_skill_run": True})
    _write_json(
        budget_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {
                "scheduler_guarded_skill_run": {
                    "window": "daily",
                    "limit": 1,
                    "used": 0,
                    "window_start_utc": None,
                },
                "low_risk_pr_merge": {
                    "window": "daily",
                    "limit": 5,
                    "used": 0,
                    "window_start_utc": None,
                },
            },
        },
    )

    emitted: list[dict] = []

    def _fake_emit(event: dict) -> dict:
        emitted.append(event)
        return {"transport": "test", "ok": True}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", _fake_emit)

    first_buf = io.StringIO()
    with redirect_stdout(first_buf):
        first_code = cli.main(
            [
                "--json",
                "autonomy",
                "scheduler",
                "tick",
                "--jobs-path",
                str(jobs_path),
                "--state-path",
                str(state_path),
                "--capability-ledger-path",
                str(ledger_path),
                "--budget-state-path",
                str(budget_path),
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    second_buf = io.StringIO()
    with redirect_stdout(second_buf):
        second_code = cli.main(
            [
                "--json",
                "autonomy",
                "scheduler",
                "tick",
                "--jobs-path",
                str(jobs_path),
                "--state-path",
                str(state_path),
                "--capability-ledger-path",
                str(ledger_path),
                "--budget-state-path",
                str(budget_path),
                "--now",
                "2026-02-25T12:01:00Z",
            ]
        )

    assert first_code == 0
    assert second_code == 0

    first_payload = json.loads(first_buf.getvalue().strip())
    second_payload = json.loads(second_buf.getvalue().strip())

    assert first_payload["guarded_runs"][0]["outcome"] == "ok"

    denied = second_payload["guarded_runs"][0]
    assert denied["outcome"] == "deny"
    assert denied["reason_code"] == "DENY_BUDGET_EXCEEDED"
    assert denied["budget_key"] == "scheduler_guarded_skill_run"

    assert len(emitted) == 2
    assert emitted[1]["type"] == "scheduler.job_due"
    assert emitted[1]["job_id"] == "nightly_audit"

    budget_payload = json.loads(budget_path.read_text(encoding="utf-8"))
    assert budget_payload["budgets"]["scheduler_guarded_skill_run"]["used"] == 1

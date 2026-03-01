from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from supervisor import cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _guarded_job(task: str) -> dict:
    return {
        "job_id": "guarded_job",
        "enabled": True,
        "schedule": {"type": "interval_minutes", "every": 5},
        "event_type": "scheduler.job_due",
        "payload": {"task": task},
        "mode": "guarded_skill",
    }


def test_guarded_skill_denied_without_capability(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    _write_json(jobs_path, {"version": "v0.1", "timezone": "UTC", "jobs": [_guarded_job("nightly_audit")]})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", lambda event: {"ok": True, "event": event})

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
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
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload["status"] == "ok"
    assert payload["guarded_runs"][0]["outcome"] == "deny"
    assert payload["guarded_runs"][0]["reason_code"] == "DENY_CAPABILITY_MISSING"


def test_guarded_skill_runs_with_capability_and_writes_artifact(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    _write_json(jobs_path, {"version": "v0.1", "timezone": "UTC", "jobs": [_guarded_job("nightly_audit")]})
    _write_json(
        ledger_path,
        {
            "scheduler_guarded_skill_run": {
                "granted": True,
                "expires_at": "2026-12-31T00:00:00Z",
            }
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", lambda event: {"ok": True, "event": event})

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
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
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    run = payload["guarded_runs"][0]
    assert run["outcome"] == "ok"
    assert run["handler_result"]["task"] == "nightly_audit"

    artifact_path = Path(run["artifact_path"])
    assert artifact_path.exists()
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["outcome"] == "ok"
    assert artifact_payload["handler_result"]["task"] == "nightly_audit"


def test_guarded_skill_denied_when_capability_expired(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    _write_json(jobs_path, {"version": "v0.1", "timezone": "UTC", "jobs": [_guarded_job("nightly_audit")]})
    _write_json(
        ledger_path,
        {
            "scheduler_guarded_skill_run": {
                "granted": True,
                "expires_at": "2026-01-01T00:00:00Z",
            }
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", lambda event: {"ok": True, "event": event})

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
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
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload["guarded_runs"][0]["outcome"] == "deny"
    assert payload["guarded_runs"][0]["reason_code"] == "DENY_CAPABILITY_EXPIRED"


def test_guarded_skill_unknown_task_denied(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    _write_json(jobs_path, {"version": "v0.1", "timezone": "UTC", "jobs": [_guarded_job("unknown_task")]})
    _write_json(ledger_path, {"scheduler_guarded_skill_run": True})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", lambda event: {"ok": True, "event": event})

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
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
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    run = payload["guarded_runs"][0]
    assert run["outcome"] == "deny"
    assert run["reason_code"] == "DENY_SCHEDULER_TASK_UNKNOWN"


def test_guarded_skill_denied_when_budget_exceeded(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    budget_path = tmp_path / "state" / "budgets.json"
    _write_json(jobs_path, {"version": "v0.1", "timezone": "UTC", "jobs": [_guarded_job("nightly_audit")]})
    _write_json(ledger_path, {"scheduler_guarded_skill_run": True})
    _write_json(
        budget_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {
                "scheduler_guarded_skill_run": {
                    "window": "daily",
                    "limit": 0,
                    "used": 0,
                    "window_start_utc": "2026-02-25T00:00:00Z",
                },
                "low_risk_pr_merge": {
                    "window": "daily",
                    "limit": 5,
                    "used": 0,
                    "window_start_utc": "2026-02-25T00:00:00Z",
                },
            },
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", lambda event: {"ok": True, "event": event})

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
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

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    run = payload["guarded_runs"][0]
    assert run["outcome"] == "deny"
    assert run["reason_code"] == "DENY_BUDGET_EXCEEDED"

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from supervisor import cli


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_scheduler_tick_dry_run_makes_no_writes(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    budget_state_path = tmp_path / "state" / "budgets.json"
    _write_json(
        jobs_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "jobs": [
                {
                    "job_id": "nightly_audit",
                    "enabled": True,
                    "schedule": {"type": "interval_minutes", "every": 1440},
                    "event_type": "scheduler.job_due",
                    "payload": {"task": "nightly_audit"},
                    "mode": "event_only",
                }
            ],
        },
    )
    _write_json(
        budget_state_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {
                "scheduler_guarded_skill_run": {
                    "window": "daily",
                    "limit": 20,
                    "used": 0,
                    "window_start_utc": None,
                }
            },
        },
    )

    monkeypatch.chdir(tmp_path)
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
                "--budget-state-path",
                str(budget_state_path),
                "--now",
                "2026-02-25T12:00:00Z",
                "--dry-run",
            ]
        )

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert len(payload["due_events"]) == 1
    assert not state_path.exists()


def test_scheduler_tick_writes_state_and_emits_envelope(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    budget_state_path = tmp_path / "state" / "budgets.json"
    _write_json(
        jobs_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "jobs": [
                {
                    "job_id": "z_job",
                    "enabled": True,
                    "schedule": {"type": "interval_minutes", "every": 10},
                    "event_type": "scheduler.job_due",
                    "payload": {"task": "z"},
                    "mode": "event_only",
                },
                {
                    "job_id": "a_job",
                    "enabled": True,
                    "schedule": {"type": "interval_minutes", "every": 10},
                    "event_type": "scheduler.job_due",
                    "payload": {"task": "a"},
                    "mode": "event_only",
                },
            ],
        },
    )
    _write_json(
        budget_state_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {
                "scheduler_guarded_skill_run": {
                    "window": "daily",
                    "limit": 20,
                    "used": 0,
                    "window_start_utc": None,
                }
            },
        },
    )

    emitted: list[dict] = []

    def _fake_emit(event: dict) -> dict:
        emitted.append(event)
        return {"transport": "test", "ok": True}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("supervisor.cli._emit_scheduler_event", _fake_emit)

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
                "--budget-state-path",
                str(budget_state_path),
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    assert code == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload["status"] == "ok"

    assert [item["job_id"] for item in emitted] == ["a_job", "z_job"]
    assert emitted[0] == {
        "type": "scheduler.job_due",
        "job_id": "a_job",
        "payload": {"task": "a"},
        "fired_at": "2026-02-25T12:00:00Z",
    }

    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_payload == {
        "version": "v0.1",
        "last_run_utc": "2026-02-25T12:00:00Z",
        "jobs": {
            "a_job": {"last_fired_utc": "2026-02-25T12:00:00Z"},
            "z_job": {"last_fired_utc": "2026-02-25T12:00:00Z"},
        },
    }


def test_scheduler_tick_halts_when_interrupt_flag_set(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    budget_state_path = tmp_path / "state" / "budgets.json"
    autonomy_state_path = tmp_path / "state" / "autonomy_state.json"
    _write_json(
        jobs_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "jobs": [
                {
                    "job_id": "nightly_audit",
                    "enabled": True,
                    "schedule": {"type": "interval_minutes", "every": 1440},
                    "event_type": "scheduler.job_due",
                    "payload": {"task": "nightly_audit"},
                    "mode": "event_only",
                }
            ],
        },
    )
    _write_json(
        budget_state_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {
                "scheduler_guarded_skill_run": {
                    "window": "daily",
                    "limit": 20,
                    "used": 0,
                    "window_start_utc": None,
                }
            },
        },
    )
    _write_json(autonomy_state_path, {"INTERRUPT_FLAG": True})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUPERVISOR_AUTONOMY_STATE_PATH", str(autonomy_state_path))

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
                "--budget-state-path",
                str(budget_state_path),
                "--now",
                "2026-02-25T12:00:00Z",
            ]
        )

    assert code == 2
    payload = json.loads(buf.getvalue().strip())
    assert payload["status"] == "halted"
    assert payload["reason_code"] == "DENY_INTERRUPT_REQUESTED"
    assert Path(payload["artifact_path"]).exists()


def test_scheduler_tick_denies_when_budget_state_is_tampered(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "state" / "scheduler_jobs.json"
    state_path = tmp_path / "state" / "scheduler_state.json"
    budget_state_path = tmp_path / "state" / "budgets.json"
    autonomy_state_path = tmp_path / "state" / "autonomy_state.json"
    integrity_metadata_path = tmp_path / "state" / "supervisor" / "state_integrity.json"
    _write_json(
        jobs_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "jobs": [
                {
                    "job_id": "nightly_audit",
                    "enabled": True,
                    "schedule": {"type": "interval_minutes", "every": 1440},
                    "event_type": "scheduler.job_due",
                    "payload": {"task": "nightly_audit"},
                    "mode": "event_only",
                }
            ],
        },
    )
    _write_json(
        budget_state_path,
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {
                "scheduler_guarded_skill_run": {
                    "window": "daily",
                    "limit": 20,
                    "used": 0,
                    "window_start_utc": None,
                }
            },
        },
    )
    _write_json(autonomy_state_path, {"INTERRUPT_FLAG": False})

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUPERVISOR_AUTONOMY_STATE_PATH", str(autonomy_state_path))
    monkeypatch.setenv("SUPERVISOR_INTEGRITY_METADATA_PATH", str(integrity_metadata_path))

    buf = io.StringIO()
    with redirect_stdout(buf):
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
                "--budget-state-path",
                str(budget_state_path),
                "--now",
                "2026-02-25T12:00:00Z",
                "--dry-run",
            ]
        )
    assert first_code == 0

    budget_state_path.write_text('{"version":"v0.1","timezone":"UTC","budgets":{"tampered":{}}}\n', encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
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
                "--budget-state-path",
                str(budget_state_path),
                "--now",
                "2026-02-25T12:01:00Z",
                "--dry-run",
            ]
        )
    assert second_code == 2
    payload = json.loads(buf.getvalue().strip())
    assert payload["status"] == "rejected"
    assert payload["reason_code"] == "DENY_STATE_INTEGRITY"

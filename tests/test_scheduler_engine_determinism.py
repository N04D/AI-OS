from __future__ import annotations

from datetime import datetime
from datetime import timezone

from supervisor.scheduler.engine import compute_due_jobs


def test_scheduler_engine_deterministic_due_and_lexical_order() -> None:
    config = {
        "version": "v0.1",
        "timezone": "UTC",
        "jobs": [
            {
                "job_id": "z_job",
                "enabled": True,
                "schedule": {"type": "interval_minutes", "every": 5},
                "event_type": "scheduler.job_due",
                "payload": {"task": "z"},
                "mode": "event_only",
            },
            {
                "job_id": "a_job",
                "enabled": True,
                "schedule": {"type": "interval_minutes", "every": 5},
                "event_type": "scheduler.job_due",
                "payload": {"task": "a"},
                "mode": "event_only",
            },
        ],
    }
    state = {
        "version": "v0.1",
        "last_run_utc": "2026-02-25T12:00:00Z",
        "jobs": {},
    }
    now_utc = datetime(2026, 2, 25, 12, 10, 0, tzinfo=timezone.utc)

    due_1, state_1 = compute_due_jobs(config=config, state=state, now_utc=now_utc)
    due_2, state_2 = compute_due_jobs(config=config, state=state, now_utc=now_utc)

    assert due_1 == due_2
    assert state_1 == state_2
    assert [item["job_id"] for item in due_1] == ["a_job", "z_job"]

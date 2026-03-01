from __future__ import annotations

from supervisor.budgets.store import save_budget_state
from supervisor.scheduler.state import write_scheduler_state


def test_budget_state_serialization_is_deterministic(tmp_path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"

    payload_a = {
        "version": "v0.1",
        "timezone": "UTC",
        "budgets": {
            "z_key": {"window": "daily", "limit": 2, "used": 1, "window_start_utc": "2026-02-27T00:00:00Z"},
            "a_key": {"window": "daily", "limit": 1, "used": 0, "window_start_utc": None},
        },
    }
    payload_b = {
        "timezone": "UTC",
        "budgets": {
            "a_key": {"used": 0, "limit": 1, "window": "daily", "window_start_utc": None},
            "z_key": {"window_start_utc": "2026-02-27T00:00:00Z", "window": "daily", "used": 1, "limit": 2},
        },
        "version": "v0.1",
    }

    save_budget_state(left, payload_a)
    save_budget_state(right, payload_b)

    assert left.read_text(encoding="utf-8") == right.read_text(encoding="utf-8")


def test_scheduler_state_serialization_is_deterministic(tmp_path) -> None:
    left = tmp_path / "left_scheduler.json"
    right = tmp_path / "right_scheduler.json"

    payload_a = {
        "version": "v0.1",
        "last_run_utc": "2026-02-27T12:00:00Z",
        "jobs": {
            "z_job": {"last_fired_utc": "2026-02-27T11:00:00Z"},
            "a_job": {"last_fired_utc": "2026-02-27T10:00:00Z"},
        },
    }
    payload_b = {
        "jobs": {
            "a_job": {"last_fired_utc": "2026-02-27T10:00:00Z"},
            "z_job": {"last_fired_utc": "2026-02-27T11:00:00Z"},
        },
        "version": "v0.1",
        "last_run_utc": "2026-02-27T12:00:00Z",
    }

    write_scheduler_state(left, payload_a)
    write_scheduler_state(right, payload_b)

    assert left.read_text(encoding="utf-8") == right.read_text(encoding="utf-8")

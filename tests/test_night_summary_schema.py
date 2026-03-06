from __future__ import annotations

import pytest

from supervisor.night_summary_schema import validate_night_summary


def test_validate_night_summary_accepts_valid_payload() -> None:
    payload = {
        "epoch": "2026-03-05",
        "tasks_executed": 1,
        "tasks_skipped": 0,
        "tasks_failed": 0,
        "budget_used": 1,
        "violations": [],
        "stopped": False,
    }
    normalized = validate_night_summary(payload)
    assert normalized == payload


def test_validate_night_summary_rejects_missing_keys() -> None:
    payload = {
        "epoch": "2026-03-05",
        "tasks_executed": 1,
    }
    with pytest.raises(ValueError, match="night_summary_missing_keys"):
        validate_night_summary(payload)


def test_validate_night_summary_rejects_invalid_types() -> None:
    payload = {
        "epoch": "2026-03-05",
        "tasks_executed": -1,
        "tasks_skipped": 0,
        "tasks_failed": 0,
        "budget_used": 0,
        "violations": [],
        "stopped": False,
    }
    with pytest.raises(ValueError, match="night_summary_invalid_tasks_executed"):
        validate_night_summary(payload)

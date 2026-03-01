from __future__ import annotations

import pytest

from supervisor.scheduler.config import SchedulerError
from supervisor.scheduler.config import validate_scheduler_config


def _valid_config() -> dict:
    return {
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
    }


def test_scheduler_schema_valid_config_passes() -> None:
    normalized = validate_scheduler_config(_valid_config())
    assert normalized["version"] == "v0.1"
    assert normalized["timezone"] == "UTC"
    assert normalized["jobs"][0]["job_id"] == "nightly_audit"


def test_scheduler_schema_invalid_schedule_type_denied() -> None:
    payload = _valid_config()
    payload["jobs"][0]["schedule"]["type"] = "cron"

    with pytest.raises(SchedulerError) as exc:
        validate_scheduler_config(payload)

    assert exc.value.reason_code == "DENY_SCHEDULER_CONFIG_INVALID"

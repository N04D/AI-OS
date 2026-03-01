from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SCHEDULER_JOBS_PATH = Path("state/scheduler_jobs.json")

DENY_SCHEDULER_CONFIG_INVALID = "DENY_SCHEDULER_CONFIG_INVALID"
DENY_SCHEDULER_STATE_INVALID = "DENY_SCHEDULER_STATE_INVALID"
DENY_SCHEDULER_TIME_INVALID = "DENY_SCHEDULER_TIME_INVALID"
DENY_SCHEDULER_MODE_UNSUPPORTED_V0 = "DENY_SCHEDULER_MODE_UNSUPPORTED_V0"


class SchedulerError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        message = reason_code if not detail else f"{reason_code}: {detail}"
        super().__init__(message)


def parse_utc_iso8601(value: str, reason_code: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise SchedulerError(reason_code, "timestamp must be non-empty string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchedulerError(reason_code, f"invalid timestamp: {value}") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchedulerError(reason_code, f"timestamp must be UTC: {value}")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise SchedulerError(reason_code, f"timestamp must be UTC: {value}")
    return parsed.astimezone(UTC)


def format_utc_iso8601(value: datetime) -> str:
    safe = value.astimezone(UTC).replace(microsecond=0)
    return safe.isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"missing scheduler config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"invalid scheduler config json: {path}") from exc


def _require_keys(payload: dict[str, Any], required: set[str], code: str, ctx: str) -> None:
    if set(payload.keys()) != required:
        raise SchedulerError(code, f"{ctx} keys must be {sorted(required)}")


def _require_bool(value: Any, code: str, ctx: str) -> bool:
    if isinstance(value, bool):
        return value
    raise SchedulerError(code, f"{ctx} must be bool")


def _require_str(value: Any, code: str, ctx: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise SchedulerError(code, f"{ctx} must be non-empty string")


def validate_scheduler_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, "scheduler config must be object")

    _require_keys(payload, {"version", "timezone", "jobs"}, DENY_SCHEDULER_CONFIG_INVALID, "root")

    version = _require_str(payload.get("version"), DENY_SCHEDULER_CONFIG_INVALID, "version")
    timezone = _require_str(payload.get("timezone"), DENY_SCHEDULER_CONFIG_INVALID, "timezone")
    if version != "v0.1":
        raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, "version must be v0.1")
    if timezone != "UTC":
        raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, "timezone must be UTC")

    jobs_raw = payload.get("jobs")
    if not isinstance(jobs_raw, list):
        raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, "jobs must be array")

    seen_job_ids: set[str] = set()
    jobs: list[dict[str, Any]] = []
    for index, item in enumerate(jobs_raw):
        if not isinstance(item, dict):
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}] must be object")
        _require_keys(
            item,
            {"job_id", "enabled", "schedule", "event_type", "payload", "mode"},
            DENY_SCHEDULER_CONFIG_INVALID,
            f"jobs[{index}]",
        )

        job_id = _require_str(item.get("job_id"), DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].job_id")
        if job_id in seen_job_ids:
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"duplicate job_id: {job_id}")
        seen_job_ids.add(job_id)

        enabled = _require_bool(item.get("enabled"), DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].enabled")

        schedule = item.get("schedule")
        if not isinstance(schedule, dict):
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].schedule must be object")
        _require_keys(
            schedule,
            {"type", "every"},
            DENY_SCHEDULER_CONFIG_INVALID,
            f"jobs[{index}].schedule",
        )
        schedule_type = _require_str(
            schedule.get("type"),
            DENY_SCHEDULER_CONFIG_INVALID,
            f"jobs[{index}].schedule.type",
        )
        if schedule_type != "interval_minutes":
            raise SchedulerError(
                DENY_SCHEDULER_CONFIG_INVALID,
                f"jobs[{index}].schedule.type must be interval_minutes",
            )
        every = schedule.get("every")
        if not isinstance(every, int) or every <= 0:
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].schedule.every must be > 0 int")

        event_type = _require_str(item.get("event_type"), DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].event_type")
        if event_type != "scheduler.job_due":
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].event_type must be scheduler.job_due")

        payload_raw = item.get("payload")
        if not isinstance(payload_raw, dict):
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].payload must be object")

        mode = _require_str(item.get("mode"), DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].mode")
        if mode not in {"event_only", "guarded_skill"}:
            raise SchedulerError(DENY_SCHEDULER_CONFIG_INVALID, f"jobs[{index}].mode unsupported")
        if mode == "guarded_skill":
            task_name = payload_raw.get("task")
            if not isinstance(task_name, str) or not task_name:
                raise SchedulerError(
                    DENY_SCHEDULER_CONFIG_INVALID,
                    f"jobs[{index}].payload.task required for guarded_skill",
                )

        jobs.append(
            {
                "job_id": job_id,
                "enabled": enabled,
                "schedule": {"type": "interval_minutes", "every": every},
                "event_type": event_type,
                "payload": payload_raw,
                "mode": mode,
            }
        )

    jobs.sort(key=lambda j: str(j["job_id"]))
    return {"version": "v0.1", "timezone": "UTC", "jobs": jobs}


def load_scheduler_config(path: Path = DEFAULT_SCHEDULER_JOBS_PATH) -> dict[str, Any]:
    return validate_scheduler_config(_read_json(path))

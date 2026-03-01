from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from supervisor.scheduler.config import DENY_SCHEDULER_STATE_INVALID
from supervisor.scheduler.config import SchedulerError
from supervisor.scheduler.config import format_utc_iso8601
from supervisor.scheduler.config import parse_utc_iso8601

DEFAULT_SCHEDULER_STATE_PATH = Path("state/scheduler_state.json")


def _default_state() -> dict[str, Any]:
    return {
        "version": "v0.1",
        "last_run_utc": None,
        "jobs": {},
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _default_state()
    except json.JSONDecodeError as exc:
        raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, f"invalid scheduler state json: {path}") from exc


def validate_scheduler_state(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, "scheduler state must be object")

    required = {"version", "last_run_utc", "jobs"}
    if set(payload.keys()) != required:
        raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, f"state keys must be {sorted(required)}")

    version = payload.get("version")
    if version != "v0.1":
        raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, "state version must be v0.1")

    last_run_raw = payload.get("last_run_utc")
    if last_run_raw is not None:
        parse_utc_iso8601(last_run_raw, DENY_SCHEDULER_STATE_INVALID)
        last_run = format_utc_iso8601(parse_utc_iso8601(last_run_raw, DENY_SCHEDULER_STATE_INVALID))
    else:
        last_run = None

    jobs_raw = payload.get("jobs")
    if not isinstance(jobs_raw, dict):
        raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, "state.jobs must be object")

    jobs: dict[str, dict[str, str]] = {}
    for job_id in sorted(jobs_raw.keys()):
        if not isinstance(job_id, str) or not job_id:
            raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, "state.jobs keys must be non-empty strings")
        entry = jobs_raw.get(job_id)
        if not isinstance(entry, dict) or set(entry.keys()) != {"last_fired_utc"}:
            raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, f"state.jobs[{job_id}] must have only last_fired_utc")
        last_fired_raw = entry.get("last_fired_utc")
        if not isinstance(last_fired_raw, str) or not last_fired_raw:
            raise SchedulerError(DENY_SCHEDULER_STATE_INVALID, f"state.jobs[{job_id}].last_fired_utc invalid")
        last_fired = format_utc_iso8601(parse_utc_iso8601(last_fired_raw, DENY_SCHEDULER_STATE_INVALID))
        jobs[job_id] = {"last_fired_utc": last_fired}

    return {
        "version": "v0.1",
        "last_run_utc": last_run,
        "jobs": jobs,
    }


def load_scheduler_state(path: Path = DEFAULT_SCHEDULER_STATE_PATH) -> dict[str, Any]:
    return validate_scheduler_state(_read_json(path))


def write_scheduler_state(path: Path, payload: dict[str, Any]) -> None:
    normalized = validate_scheduler_state(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")

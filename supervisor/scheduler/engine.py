from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Any

from supervisor.scheduler.config import DENY_SCHEDULER_TIME_INVALID
from supervisor.scheduler.config import SchedulerError
from supervisor.scheduler.config import format_utc_iso8601
from supervisor.scheduler.config import parse_utc_iso8601


def _reference_time(last_run_utc: str | None, last_fired_utc: str | None) -> datetime | None:
    refs: list[datetime] = []
    if isinstance(last_run_utc, str) and last_run_utc:
        refs.append(parse_utc_iso8601(last_run_utc, DENY_SCHEDULER_TIME_INVALID))
    if isinstance(last_fired_utc, str) and last_fired_utc:
        refs.append(parse_utc_iso8601(last_fired_utc, DENY_SCHEDULER_TIME_INVALID))
    if not refs:
        return None
    refs.sort()
    return refs[-1]


def _is_due(last_ref: datetime | None, now_utc: datetime, every_minutes: int) -> bool:
    if last_ref is None:
        return True
    delta_seconds = (now_utc - last_ref).total_seconds()
    if delta_seconds < 0:
        return False
    return delta_seconds >= (every_minutes * 60)


def compute_due_jobs(config: dict[str, Any], state: dict[str, Any], now_utc: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise SchedulerError(DENY_SCHEDULER_TIME_INVALID, "now_utc must be timezone-aware UTC")

    safe_now_utc = now_utc.astimezone(UTC)
    if safe_now_utc.utcoffset() != UTC.utcoffset(safe_now_utc):
        raise SchedulerError(DENY_SCHEDULER_TIME_INVALID, "now_utc must be UTC")

    now_iso = format_utc_iso8601(safe_now_utc)
    due_events: list[dict[str, Any]] = []

    next_state_jobs: dict[str, dict[str, str]] = {
        str(job_id): {"last_fired_utc": str(entry.get("last_fired_utc"))}
        for job_id, entry in sorted((state.get("jobs") or {}).items())
        if isinstance(job_id, str) and isinstance(entry, dict) and isinstance(entry.get("last_fired_utc"), str)
    }

    last_run_utc = state.get("last_run_utc")

    for job in sorted(config.get("jobs") or [], key=lambda item: str(item.get("job_id", ""))):
        job_id = str(job.get("job_id", ""))
        if not job_id:
            continue
        if not bool(job.get("enabled", False)):
            continue

        schedule = job.get("schedule") or {}
        every = int(schedule.get("every", 0) or 0)
        if every <= 0:
            continue

        existing = next_state_jobs.get(job_id, {})
        last_fired_utc = existing.get("last_fired_utc") if isinstance(existing, dict) else None
        ref = _reference_time(last_run_utc if isinstance(last_run_utc, str) else None, last_fired_utc)
        if not _is_due(ref, safe_now_utc, every):
            continue

        due_events.append(
            {
                "type": str(job.get("event_type", "scheduler.job_due")),
                "job_id": job_id,
                "payload": job.get("payload") if isinstance(job.get("payload"), dict) else {},
                "mode": str(job.get("mode", "event_only")),
                "fired_at": now_iso,
            }
        )
        next_state_jobs[job_id] = {"last_fired_utc": now_iso}

    next_state = {
        "version": "v0.1",
        "last_run_utc": now_iso,
        "jobs": {job_id: next_state_jobs[job_id] for job_id in sorted(next_state_jobs.keys())},
    }
    return due_events, next_state

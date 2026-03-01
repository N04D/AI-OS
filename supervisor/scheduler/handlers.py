from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Callable

DENY_SCHEDULER_TASK_UNKNOWN = "DENY_SCHEDULER_TASK_UNKNOWN"
DENY_SCHEDULER_TASK_FAILED = "DENY_SCHEDULER_TASK_FAILED"


class SchedulerTaskError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _nightly_audit(payload: dict[str, Any], now_utc: datetime | None = None) -> dict[str, Any]:
    safe_now = now_utc.astimezone(UTC) if isinstance(now_utc, datetime) else datetime.now(UTC)
    return {
        "task": "nightly_audit",
        "checked_keys": sorted(payload.keys()),
        "executed_at": safe_now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


HANDLERS: dict[str, Callable[[dict[str, Any], datetime | None], dict[str, Any]]] = {
    "nightly_audit": _nightly_audit,
}


def dispatch_task(task_name: str, payload: dict[str, Any], now_utc: datetime | None = None) -> dict[str, Any]:
    handler = HANDLERS.get(task_name)
    if handler is None:
        raise SchedulerTaskError(DENY_SCHEDULER_TASK_UNKNOWN, f"unknown task: {task_name}")

    try:
        return handler(payload, now_utc)
    except SchedulerTaskError:
        raise
    except Exception as exc:
        raise SchedulerTaskError(DENY_SCHEDULER_TASK_FAILED, str(exc)) from exc

from __future__ import annotations

from typing import Any


REQUIRED_KEYS: tuple[str, ...] = (
    "epoch",
    "tasks_executed",
    "tasks_skipped",
    "tasks_failed",
    "budget_used",
    "violations",
    "stopped",
)


def validate_night_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("night_summary_invalid_type")

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise ValueError(f"night_summary_missing_keys:{','.join(missing)}")

    epoch = payload.get("epoch")
    if not isinstance(epoch, str) or len(epoch) != 10:
        raise ValueError("night_summary_invalid_epoch")

    for key in ("tasks_executed", "tasks_skipped", "tasks_failed", "budget_used"):
        value = payload.get(key)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"night_summary_invalid_{key}")

    violations = payload.get("violations")
    if not isinstance(violations, list) or any(not isinstance(item, str) for item in violations):
        raise ValueError("night_summary_invalid_violations")

    stopped = payload.get("stopped")
    if not isinstance(stopped, bool):
        raise ValueError("night_summary_invalid_stopped")

    return {
        "epoch": epoch,
        "tasks_executed": int(payload["tasks_executed"]),
        "tasks_skipped": int(payload["tasks_skipped"]),
        "tasks_failed": int(payload["tasks_failed"]),
        "budget_used": int(payload["budget_used"]),
        "violations": list(violations),
        "stopped": bool(stopped),
    }

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

DENY_BUDGET_EXCEEDED = "DENY_BUDGET_EXCEEDED"
DENY_BUDGET_STATE_INVALID = "DENY_BUDGET_STATE_INVALID"

DEFAULT_BUDGETS_PATH = Path("state/budgets.json")
DEFAULT_LIMITS = {
    "governed_commit": 5,
    "scheduler_guarded_skill": 20,
}


class BudgetError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        message = reason_code if not detail else f"{reason_code}: {detail}"
        super().__init__(message)


def _require_utc(now_utc: datetime) -> datetime:
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "now_utc must be timezone-aware")
    safe = now_utc.astimezone(UTC)
    if safe.utcoffset() != UTC.utcoffset(safe):
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "now_utc must be UTC")
    return safe


def _utc_day(now_utc: datetime) -> str:
    return _require_utc(now_utc).strftime("%Y-%m-%d")


def _new_state(now_utc: datetime) -> dict[str, Any]:
    day = _utc_day(now_utc)
    return {
        "version": "v0.1",
        "window_utc_day": day,
        "limits": dict(sorted(DEFAULT_LIMITS.items())),
        "counts": {k: 0 for k in sorted(DEFAULT_LIMITS.keys())},
    }


def _validate_state(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "budget state must be object")

    if set(payload.keys()) != {"version", "window_utc_day", "limits", "counts"}:
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "budget state keys invalid")

    if payload.get("version") != "v0.1":
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "budget state version invalid")

    day = payload.get("window_utc_day")
    if not isinstance(day, str) or len(day) != 10:
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "window_utc_day invalid")

    limits = payload.get("limits")
    counts = payload.get("counts")
    if not isinstance(limits, dict) or not isinstance(counts, dict):
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "limits/counts must be objects")

    if set(limits.keys()) != set(DEFAULT_LIMITS.keys()):
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "limits keys invalid")
    if set(counts.keys()) != set(DEFAULT_LIMITS.keys()):
        raise BudgetError(DENY_BUDGET_STATE_INVALID, "counts keys invalid")

    normalized_limits: dict[str, int] = {}
    normalized_counts: dict[str, int] = {}
    for key in sorted(DEFAULT_LIMITS.keys()):
        limit = limits.get(key)
        count = counts.get(key)
        if not isinstance(limit, int) or limit < 0:
            raise BudgetError(DENY_BUDGET_STATE_INVALID, f"limit invalid: {key}")
        if not isinstance(count, int) or count < 0:
            raise BudgetError(DENY_BUDGET_STATE_INVALID, f"count invalid: {key}")
        normalized_limits[key] = limit
        normalized_counts[key] = count

    return {
        "version": "v0.1",
        "window_utc_day": day,
        "limits": normalized_limits,
        "counts": normalized_counts,
    }


def load_budget_state(path: Path = DEFAULT_BUDGETS_PATH, *, now_utc: datetime) -> dict[str, Any]:
    if not path.exists():
        return _new_state(now_utc)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BudgetError(DENY_BUDGET_STATE_INVALID, f"invalid budget json: {path}") from exc
    return _validate_state(payload)


def write_budget_state(path: Path, state: dict[str, Any]) -> None:
    normalized = _validate_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def consume_budget(action: str, *, now_utc: datetime, path: Path = DEFAULT_BUDGETS_PATH) -> dict[str, Any]:
    if action not in DEFAULT_LIMITS:
        raise BudgetError(DENY_BUDGET_STATE_INVALID, f"unknown action: {action}")

    safe_now = _require_utc(now_utc)
    state = load_budget_state(path=path, now_utc=safe_now)
    day = _utc_day(safe_now)

    if state["window_utc_day"] != day:
        state = _new_state(safe_now)

    count = int(state["counts"][action])
    limit = int(state["limits"][action])
    if count >= limit:
        write_budget_state(path, state)
        return {
            "allowed": False,
            "reason_code": DENY_BUDGET_EXCEEDED,
            "state": state,
        }

    state["counts"][action] = count + 1
    write_budget_state(path, state)
    return {
        "allowed": True,
        "reason_code": None,
        "state": state,
    }

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

DENY_BUDGET_STATE_INVALID = "DENY_BUDGET_STATE_INVALID"
DENY_BUDGET_EXCEEDED = "DENY_BUDGET_EXCEEDED"

DEFAULT_BUDGETS_PATH = Path("state/budgets.json")

DEFAULT_BUDGETS = {
    "scheduler_guarded_skill_run": {
        "window": "daily",
        "limit": 20,
        "used": 0,
        "window_start_utc": None,
    },
    "low_risk_pr_merge": {
        "window": "daily",
        "limit": 5,
        "used": 0,
        "window_start_utc": None,
    },
}


class BudgetStateError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        msg = reason_code if not detail else f"{reason_code}: {detail}"
        super().__init__(msg)


def _ensure_utc(now_utc: datetime) -> datetime:
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "now_utc must be timezone-aware")
    if now_utc.utcoffset() != UTC.utcoffset(now_utc):
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "now_utc must be UTC")
    return now_utc.astimezone(UTC)


def _parse_iso8601_z(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"invalid timestamp: {value}")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"timestamp must be UTC: {value}")
    return parsed.astimezone(UTC)


def _day_start_utc(now_utc: datetime) -> datetime:
    safe = _ensure_utc(now_utc)
    return datetime(safe.year, safe.month, safe.day, tzinfo=UTC)


def _to_iso8601_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_budget_state() -> dict[str, Any]:
    return {
        "version": "v0.1",
        "timezone": "UTC",
        "budgets": {
            key: {
                "window": "daily",
                "limit": int(entry["limit"]),
                "used": 0,
                "window_start_utc": None,
            }
            for key, entry in sorted(DEFAULT_BUDGETS.items())
        },
    }


def validate_budget_state(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "budget state must be object")
    if set(payload.keys()) != {"version", "timezone", "budgets"}:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "budget state keys invalid")
    if payload.get("version") != "v0.1":
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "version must be v0.1")
    if payload.get("timezone") != "UTC":
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "timezone must be UTC")

    budgets = payload.get("budgets")
    if not isinstance(budgets, dict):
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "budgets must be object")

    normalized: dict[str, dict[str, Any]] = {}
    for key in sorted(budgets.keys()):
        if not isinstance(key, str) or not key:
            raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "budget key must be non-empty string")
        entry = budgets.get(key)
        if not isinstance(entry, dict):
            raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"budget entry invalid: {key}")
        if set(entry.keys()) != {"window", "limit", "used", "window_start_utc"}:
            raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"budget entry keys invalid: {key}")

        window = entry.get("window")
        limit = entry.get("limit")
        used = entry.get("used")
        window_start_utc = entry.get("window_start_utc")

        if window != "daily":
            raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"window must be daily: {key}")
        if not isinstance(limit, int) or limit < 0:
            raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"limit invalid: {key}")
        if not isinstance(used, int) or used < 0:
            raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"used invalid: {key}")
        if window_start_utc is not None:
            if not isinstance(window_start_utc, str) or not window_start_utc:
                raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"window_start_utc invalid: {key}")
            _parse_iso8601_z(window_start_utc)

        normalized[key] = {
            "window": "daily",
            "limit": limit,
            "used": used,
            "window_start_utc": window_start_utc,
        }

    return {
        "version": "v0.1",
        "timezone": "UTC",
        "budgets": normalized,
    }


def load_budget_state(path: Path = DEFAULT_BUDGETS_PATH) -> dict[str, Any]:
    if not path.exists():
        return default_budget_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"invalid json: {path}") from exc
    return validate_budget_state(payload)


def save_budget_state(path: Path, state: dict[str, Any]) -> None:
    normalized = validate_budget_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def check_and_consume(
    budgets: dict[str, Any],
    key: str,
    now_utc: datetime,
    cost: int = 1,
) -> tuple[bool, dict[str, Any], str | None]:
    _ensure_utc(now_utc)
    if not isinstance(cost, int) or cost < 0:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, "cost must be non-negative int")
    if key not in budgets:
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"unknown budget key: {key}")

    entry = budgets.get(key)
    if not isinstance(entry, dict):
        raise BudgetStateError(DENY_BUDGET_STATE_INVALID, f"budget entry invalid: {key}")

    validated = validate_budget_state(
        {
            "version": "v0.1",
            "timezone": "UTC",
            "budgets": {key: entry},
        }
    )
    normalized_entry = validated["budgets"][key]

    day_start = _day_start_utc(now_utc)
    day_start_iso = _to_iso8601_z(day_start)

    window_start = normalized_entry.get("window_start_utc")
    if window_start is None:
        normalized_entry["window_start_utc"] = day_start_iso
    else:
        current_start = _parse_iso8601_z(window_start)
        if current_start.date() != day_start.date():
            normalized_entry["used"] = 0
            normalized_entry["window_start_utc"] = day_start_iso

    used = int(normalized_entry["used"])
    limit = int(normalized_entry["limit"])
    if (used + cost) > limit:
        budgets[key] = normalized_entry
        return False, budgets, DENY_BUDGET_EXCEEDED

    normalized_entry["used"] = used + cost
    budgets[key] = normalized_entry
    return True, budgets, None


def consume_from_path(
    path: Path,
    key: str,
    now_utc: datetime,
    cost: int = 1,
) -> dict[str, Any]:
    state = load_budget_state(path)
    before = json.dumps(state["budgets"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    ok, updated_budgets, reason_code = check_and_consume(state["budgets"], key, now_utc, cost=cost)
    state["budgets"] = updated_budgets
    after = json.dumps(state["budgets"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if ok or before != after:
        save_budget_state(path, state)

    snapshot_entry = dict(state["budgets"][key])
    snapshot = {
        "budget_key": key,
        "limit": int(snapshot_entry["limit"]),
        "used": int(snapshot_entry["used"]),
        "window_start_utc": snapshot_entry["window_start_utc"],
    }
    return {
        "ok": ok,
        "reason_code": reason_code,
        "snapshot": snapshot,
    }

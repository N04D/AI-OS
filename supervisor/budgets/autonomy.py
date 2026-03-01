from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_HOST_STATE_DIR = "/home/infra/night/state"
DEFAULT_BUDGET_STATE_PATH = f"{DEFAULT_HOST_STATE_DIR}/autonomy/budget.json"
DEFAULT_BUDGET_LOG_PATH = f"{DEFAULT_HOST_STATE_DIR}/autonomy/budget-log.jsonl"

DEFAULT_DAILY_LIMITS = {
    "promotion": 10,
    "intake": 20,
    "materialize": 20,
    "exec_attempt": 30,
    "commit": 5,
    "improvement": 8,
}

DEFAULT_COOLDOWNS_SECONDS = {
    "promotion": 60,
    "intake": 15,
    "materialize": 15,
    "exec_attempt": 5,
    "commit": 0,
    "improvement": 0,
}


def _now_epoch_s() -> int:
    return int(time.time())


def _utc_day(epoch_s: int) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).strftime("%Y-%m-%d")


def _resolve_budget_paths(
    *,
    host_state_dir: str | None = None,
    state_path: str | None = None,
    log_path: str | None = None,
) -> tuple[Path, Path]:
    root = host_state_dir or os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR
    resolved_state = Path(state_path or f"{root}/autonomy/budget.json")
    resolved_log = Path(log_path or f"{root}/autonomy/budget-log.jsonl")
    return resolved_state, resolved_log


def _write_json_fsync(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _append_jsonl_fsync(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _normalized_state(window_utc_day: str) -> dict[str, Any]:
    keys = sorted(DEFAULT_DAILY_LIMITS.keys())
    return {
        "version": "autonomy-budget.v0.1",
        "window_utc_day": window_utc_day,
        "counts": {k: 0 for k in keys},
        "last_action_epoch_s": {k: 0 for k in keys},
        "last_consume_keys": {k: "" for k in keys},
        "daily_limits": dict(sorted(DEFAULT_DAILY_LIMITS.items())),
        "cooldowns_seconds": dict(sorted(DEFAULT_COOLDOWNS_SECONDS.items())),
    }


def load_or_init_budget_state(
    *,
    host_state_dir: str | None = None,
    state_path: str | None = None,
    now_epoch_s: int | None = None,
) -> tuple[dict[str, Any], Path]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day(ts)
    resolved_state, _ = _resolve_budget_paths(host_state_dir=host_state_dir, state_path=state_path)

    if not resolved_state.is_file():
        state = _normalized_state(day)
        _write_json_fsync(resolved_state, state)
        return state, resolved_state

    loaded = json.loads(resolved_state.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("invalid_budget_state")

    state = _normalized_state(str(loaded.get("window_utc_day") or day))
    for key in state["counts"]:
        count_value = ((loaded.get("counts") or {}).get(key))
        if isinstance(count_value, int) and count_value >= 0:
            state["counts"][key] = count_value
        last_action_value = ((loaded.get("last_action_epoch_s") or {}).get(key))
        if isinstance(last_action_value, int) and last_action_value >= 0:
            state["last_action_epoch_s"][key] = last_action_value
        last_consume_value = ((loaded.get("last_consume_keys") or {}).get(key))
        if isinstance(last_consume_value, str):
            state["last_consume_keys"][key] = last_consume_value
    return state, resolved_state


def roll_window_if_needed(state: dict[str, Any], *, now_epoch_s: int | None = None) -> tuple[dict[str, Any], bool]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day(ts)
    if state.get("window_utc_day") == day:
        return state, False
    return _normalized_state(day), True


def _state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_utc_day": str(state.get("window_utc_day", "")),
        "counts": dict(sorted((state.get("counts") or {}).items())),
        "daily_limits": dict(sorted((state.get("daily_limits") or {}).items())),
        "cooldowns_seconds": dict(sorted((state.get("cooldowns_seconds") or {}).items())),
    }


def _context_key(action: str, context_id: str, ts: int) -> str:
    return f"{action}|{context_id}|{ts}"


def append_budget_event_log(
    event: dict[str, Any],
    *,
    host_state_dir: str | None = None,
    log_path: str | None = None,
) -> Path:
    _, resolved_log = _resolve_budget_paths(host_state_dir=host_state_dir, log_path=log_path)
    _append_jsonl_fsync(resolved_log, event)
    return resolved_log


def check_budget(
    action: str,
    *,
    context_id: str = "",
    now_epoch_s: int | None = None,
    host_state_dir: str | None = None,
    state_path: str | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day(ts)

    if action not in DEFAULT_DAILY_LIMITS:
        result = {
            "allowed": False,
            "reason": "unknown_action_type",
            "state": {"window_utc_day": day, "counts": {}, "daily_limits": {}, "cooldowns_seconds": {}},
        }
        append_budget_event_log(
            {
                "event": "budget_check",
                "action": action,
                "context_id": context_id,
                "allowed": False,
                "reason": result["reason"],
                "window_utc_day": day,
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return result

    try:
        state, resolved_state = load_or_init_budget_state(
            host_state_dir=host_state_dir,
            state_path=state_path,
            now_epoch_s=ts,
        )
        state, rolled = roll_window_if_needed(state, now_epoch_s=ts)
        if rolled:
            _write_json_fsync(resolved_state, state)

        count = int(state["counts"].get(action, 0))
        cooldown = int(state["cooldowns_seconds"].get(action, 0))
        last_epoch = int(state["last_action_epoch_s"].get(action, 0))
        limit = int(state["daily_limits"].get(action, 0))
        if cooldown > 0 and last_epoch > 0 and (ts - last_epoch) < cooldown:
            reason = "cooldown_active"
            allowed = False
        elif count >= limit:
            reason = "budget_exceeded"
            allowed = False
        else:
            reason = "allowed"
            allowed = True

        result = {"allowed": allowed, "reason": reason, "state": _state_snapshot(state)}
        append_budget_event_log(
            {
                "event": "budget_check",
                "action": action,
                "context_id": context_id,
                "allowed": allowed,
                "reason": reason,
                "window_utc_day": result["state"]["window_utc_day"],
                "count": count,
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return result
    except Exception as exc:
        append_budget_event_log(
            {
                "event": "budget_check",
                "action": action,
                "context_id": context_id,
                "allowed": False,
                "reason": "budget_internal_error",
                "error": type(exc).__name__,
                "window_utc_day": day,
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return {
            "allowed": False,
            "reason": "budget_internal_error",
            "state": {"window_utc_day": day, "counts": {}, "daily_limits": {}, "cooldowns_seconds": {}},
        }


def consume_budget(
    action: str,
    *,
    context_id: str = "",
    now_epoch_s: int | None = None,
    host_state_dir: str | None = None,
    state_path: str | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day(ts)

    try:
        if action not in DEFAULT_DAILY_LIMITS:
            return {
                "consumed": False,
                "reason": "unknown_action_type",
                "state": {"window_utc_day": day, "counts": {}, "daily_limits": {}, "cooldowns_seconds": {}},
            }

        state, resolved_state = load_or_init_budget_state(
            host_state_dir=host_state_dir,
            state_path=state_path,
            now_epoch_s=ts,
        )
        state, rolled = roll_window_if_needed(state, now_epoch_s=ts)
        if rolled:
            _write_json_fsync(resolved_state, state)

        idempotency_key = _context_key(action, context_id, ts)
        if context_id and state["last_consume_keys"].get(action) == idempotency_key:
            result = {"consumed": False, "reason": "duplicate_context", "state": _state_snapshot(state)}
            append_budget_event_log(
                {
                    "event": "budget_consume",
                    "action": action,
                    "context_id": context_id,
                    "consumed": False,
                    "reason": "duplicate_context",
                    "window_utc_day": result["state"]["window_utc_day"],
                    "ts_epoch_s": ts,
                },
                host_state_dir=host_state_dir,
                log_path=log_path,
            )
            return result

        count = int(state["counts"].get(action, 0))
        cooldown = int(state["cooldowns_seconds"].get(action, 0))
        last_epoch = int(state["last_action_epoch_s"].get(action, 0))
        limit = int(state["daily_limits"].get(action, 0))
        if cooldown > 0 and last_epoch > 0 and (ts - last_epoch) < cooldown:
            result = {"consumed": False, "reason": "cooldown_active", "state": _state_snapshot(state)}
            append_budget_event_log(
                {
                    "event": "budget_consume",
                    "action": action,
                    "context_id": context_id,
                    "consumed": False,
                    "reason": "cooldown_active",
                    "window_utc_day": result["state"]["window_utc_day"],
                    "count": count,
                    "ts_epoch_s": ts,
                },
                host_state_dir=host_state_dir,
                log_path=log_path,
            )
            return result
        if count >= limit:
            result = {"consumed": False, "reason": "budget_exceeded", "state": _state_snapshot(state)}
            append_budget_event_log(
                {
                    "event": "budget_consume",
                    "action": action,
                    "context_id": context_id,
                    "consumed": False,
                    "reason": "budget_exceeded",
                    "window_utc_day": result["state"]["window_utc_day"],
                    "count": count,
                    "ts_epoch_s": ts,
                },
                host_state_dir=host_state_dir,
                log_path=log_path,
            )
            return result

        state["counts"][action] = int(state["counts"].get(action, 0)) + 1
        state["last_action_epoch_s"][action] = ts
        state["last_consume_keys"][action] = idempotency_key if context_id else ""
        _write_json_fsync(resolved_state, state)
        result = {"consumed": True, "reason": "consumed", "state": _state_snapshot(state)}
        append_budget_event_log(
            {
                "event": "budget_consume",
                "action": action,
                "context_id": context_id,
                "consumed": True,
                "reason": "consumed",
                "window_utc_day": result["state"]["window_utc_day"],
                "count_after": int(state["counts"].get(action, 0)),
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return result
    except Exception as exc:
        append_budget_event_log(
            {
                "event": "budget_consume",
                "action": action,
                "context_id": context_id,
                "consumed": False,
                "reason": "budget_internal_error",
                "error": type(exc).__name__,
                "window_utc_day": day,
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return {
            "consumed": False,
            "reason": "budget_internal_error",
            "state": {"window_utc_day": day, "counts": {}, "daily_limits": {}, "cooldowns_seconds": {}},
        }


def consume_improvement_budget(
    *,
    pr_id: str,
    tier: str,
    now_epoch_s: int | None = None,
    host_state_dir: str | None = None,
    state_path: str | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    normalized_pr_id = str(pr_id).strip()
    normalized_tier = str(tier).strip().upper()
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day(ts)
    if not normalized_pr_id:
        return {
            "consumed": False,
            "reason": "invalid_pr_id",
            "state": {"window_utc_day": day, "counts": {}, "daily_limits": {}, "cooldowns_seconds": {}},
            "pr_id": normalized_pr_id,
            "tier": normalized_tier,
        }
    if normalized_tier not in {"LOW", "MED", "HIGH"}:
        return {
            "consumed": False,
            "reason": "invalid_tier",
            "state": {"window_utc_day": day, "counts": {}, "daily_limits": {}, "cooldowns_seconds": {}},
            "pr_id": normalized_pr_id,
            "tier": normalized_tier,
        }

    context_id = f"pr:{normalized_pr_id}|tier:{normalized_tier}"
    result = consume_budget(
        "improvement",
        context_id=context_id,
        now_epoch_s=ts,
        host_state_dir=host_state_dir,
        state_path=state_path,
        log_path=log_path,
    )
    append_budget_event_log(
        {
            "event": "improvement_budget_consume",
            "pr_id": normalized_pr_id,
            "tier": normalized_tier,
            "consumed": bool(result.get("consumed", False)),
            "reason": str(result.get("reason", "budget_internal_error")),
            "window_utc_day": str((result.get("state") or {}).get("window_utc_day", day)),
            "ts_epoch_s": ts,
        },
        host_state_dir=host_state_dir,
        log_path=log_path,
    )
    return {**result, "pr_id": normalized_pr_id, "tier": normalized_tier}

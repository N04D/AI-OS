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
}

DEFAULT_COOLDOWNS_SECONDS = {
    "promotion": 60,
    "intake": 15,
    "materialize": 15,
    "exec_attempt": 5,
    "commit": 0,
}


def _utc_day_from_epoch(epoch_s: int) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).strftime("%Y-%m-%d")


def _now_epoch_s() -> int:
    return int(time.time())


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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


def _normalized_state(window_utc_day: str) -> dict[str, Any]:
    return {
        "version": "autonomy-budget.v0.1",
        "window_utc_day": window_utc_day,
        "counts": {k: 0 for k in sorted(DEFAULT_DAILY_LIMITS.keys())},
        "last_action_epoch_s": {k: 0 for k in sorted(DEFAULT_DAILY_LIMITS.keys())},
        "daily_limits": dict(sorted(DEFAULT_DAILY_LIMITS.items())),
        "cooldowns_seconds": dict(sorted(DEFAULT_COOLDOWNS_SECONDS.items())),
    }


def load_or_init_budget_state(
    *,
    state_path: str | None = None,
    host_state_dir: str | None = None,
    now_epoch_s: int | None = None,
) -> tuple[dict[str, Any], Path]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day_from_epoch(ts)
    resolved_state, _ = _resolve_budget_paths(host_state_dir=host_state_dir, state_path=state_path)

    if not resolved_state.is_file():
        state = _normalized_state(day)
        _write_json_fsync(resolved_state, state)
        return state, resolved_state

    loaded = json.loads(resolved_state.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("invalid_budget_state")

    state = _normalized_state(str(loaded.get("window_utc_day") or day))
    incoming_counts = loaded.get("counts")
    incoming_last = loaded.get("last_action_epoch_s")
    if isinstance(incoming_counts, dict):
        for key in state["counts"]:
            value = incoming_counts.get(key)
            if isinstance(value, int) and value >= 0:
                state["counts"][key] = value
    if isinstance(incoming_last, dict):
        for key in state["last_action_epoch_s"]:
            value = incoming_last.get(key)
            if isinstance(value, int) and value >= 0:
                state["last_action_epoch_s"][key] = value
    return state, resolved_state


def roll_window_if_needed(
    state: dict[str, Any],
    *,
    now_epoch_s: int | None = None,
) -> tuple[dict[str, Any], bool]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day_from_epoch(ts)
    if state.get("window_utc_day") == day:
        return state, False

    state["window_utc_day"] = day
    state["counts"] = {k: 0 for k in sorted(DEFAULT_DAILY_LIMITS.keys())}
    state["last_action_epoch_s"] = {k: 0 for k in sorted(DEFAULT_DAILY_LIMITS.keys())}
    return state, True


def append_budget_event_log(
    event: dict[str, Any],
    *,
    log_path: str | None = None,
    host_state_dir: str | None = None,
) -> Path:
    _, resolved_log = _resolve_budget_paths(host_state_dir=host_state_dir, log_path=log_path)
    resolved_log.parent.mkdir(parents=True, exist_ok=True)
    with resolved_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return resolved_log


def check_and_consume(
    action_type: str,
    *,
    subject_id: str | None = None,
    now_epoch_s: int | None = None,
    host_state_dir: str | None = None,
    state_path: str | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    ts = _now_epoch_s() if now_epoch_s is None else int(now_epoch_s)
    day = _utc_day_from_epoch(ts)

    if action_type not in DEFAULT_DAILY_LIMITS:
        result = {
            "allowed": False,
            "reason": "unknown_action_type",
            "action_type": action_type,
            "counts": {},
            "window_utc_day": day,
        }
        append_budget_event_log(
            {
                "event": "budget_check",
                "allowed": False,
                "reason": "unknown_action_type",
                "action_type": action_type,
                "subject_id": subject_id or "",
                "window_utc_day": day,
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return result

    try:
        state, resolved_state = load_or_init_budget_state(
            state_path=state_path,
            host_state_dir=host_state_dir,
            now_epoch_s=ts,
        )
        state, rolled = roll_window_if_needed(state, now_epoch_s=ts)
        if rolled:
            _write_json_fsync(resolved_state, state)

        counts = state["counts"]
        last = state["last_action_epoch_s"]
        current_count = int(counts.get(action_type, 0))
        last_epoch = int(last.get(action_type, 0))
        cooldown = int(DEFAULT_COOLDOWNS_SECONDS[action_type])
        limit = int(DEFAULT_DAILY_LIMITS[action_type])

        if cooldown > 0 and last_epoch > 0 and (ts - last_epoch) < cooldown:
            reason = "cooldown_active"
            allowed = False
        elif current_count >= limit:
            reason = "daily_limit_exhausted"
            allowed = False
        else:
            reason = "allowed"
            allowed = True
            counts[action_type] = current_count + 1
            last[action_type] = ts
            _write_json_fsync(resolved_state, state)

        result = {
            "allowed": allowed,
            "reason": reason,
            "action_type": action_type,
            "counts": dict(sorted(counts.items())),
            "window_utc_day": str(state.get("window_utc_day") or day),
        }
        append_budget_event_log(
            {
                "event": "budget_check",
                "allowed": allowed,
                "reason": reason,
                "action_type": action_type,
                "subject_id": subject_id or "",
                "window_utc_day": result["window_utc_day"],
                "count_after": int(counts.get(action_type, 0)),
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
                "allowed": False,
                "reason": "budget_internal_error",
                "action_type": action_type,
                "subject_id": subject_id or "",
                "window_utc_day": day,
                "error": type(exc).__name__,
                "ts_epoch_s": ts,
            },
            host_state_dir=host_state_dir,
            log_path=log_path,
        )
        return {
            "allowed": False,
            "reason": "budget_internal_error",
            "action_type": action_type,
            "counts": {},
            "window_utc_day": day,
        }

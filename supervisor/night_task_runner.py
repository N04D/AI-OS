from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _discover_supervised_entrypoint() -> Callable[..., Any] | None:
    # Keep adapter aligned with the same supervised execution path used manually.
    try:
        from supervisor import spec_runner  # type: ignore
    except Exception:
        return None
    fn = getattr(spec_runner, "run_spec", None)
    if callable(fn):
        return fn
    return None


def execute_night_task(issue: int, spec_path: str) -> dict[str, Any]:
    ts_start_ms = _now_ms()
    spec = Path(spec_path)
    if not spec.is_file():
        ts_end_ms = _now_ms()
        return {
            "status": "failure",
            "reason": "spec_missing",
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
            "ts_start_ms": ts_start_ms,
            "ts_end_ms": ts_end_ms,
        }

    entrypoint = _discover_supervised_entrypoint()
    if entrypoint is None:
        ts_end_ms = _now_ms()
        return {
            "status": "failure",
            "reason": "executor_not_wired",
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
            "ts_start_ms": ts_start_ms,
            "ts_end_ms": ts_end_ms,
        }

    try:
        raw = entrypoint(spec_path=spec_path, issue=issue)
    except Exception as exc:
        ts_end_ms = _now_ms()
        return {
            "status": "failure",
            "reason": f"execution_error:{exc}",
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
            "ts_start_ms": ts_start_ms,
            "ts_end_ms": ts_end_ms,
        }

    ts_end_ms = _now_ms()
    if not isinstance(raw, dict):
        return {
            "status": "failure",
            "reason": "invalid_execution_payload",
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
            "ts_start_ms": ts_start_ms,
            "ts_end_ms": ts_end_ms,
        }

    status = str(raw.get("status", "failure"))
    reason = raw.get("reason")
    return {
        "status": status,
        "reason": None if status == "success" else (str(reason) if reason is not None else "execution_failed"),
        "stdout": str(raw.get("stdout", "")),
        "stderr": str(raw.get("stderr", "")),
        "changed_files": [x for x in raw.get("changed_files", []) if isinstance(x, str)],
        "tests_passed": bool(raw.get("tests_passed", False)),
        "ts_start_ms": ts_start_ms,
        "ts_end_ms": ts_end_ms,
    }

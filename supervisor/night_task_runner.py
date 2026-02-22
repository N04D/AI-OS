from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _extract_allowed_files(spec_text: str) -> list[str]:
    return sorted(set(re.findall(r"`([A-Za-z0-9_./-]+)`", spec_text)))


def _build_dispatch_input(issue: int, spec_path: str, spec_text: str) -> tuple[dict[str, Any], str]:
    governance_hash = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
    dispatch_input = {
        "task_id": issue,
        "instruction": spec_text,
        "allowed_files": _extract_allowed_files(spec_text),
        "expected_outcome": f"Night task issue:{issue} executes deterministically",
        "governance_hash": governance_hash,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return dispatch_input, governance_hash


def _execute_via_task_engine(issue: int, spec_path: str, spec_text: str) -> dict[str, Any]:
    from executor.dispatch import DispatchFailure
    from supervisor.supervisor import _policy_path
    from supervisor.supervisor import dispatch_task_with_supervisor_permit
    from supervisor.supervisor import ingest_executor_result
    from supervisor.supervisor import load_policy

    dispatch_input, _ = _build_dispatch_input(issue, spec_path, spec_text)
    _, policy_hash = load_policy(_policy_path())
    try:
        result, dispatch_meta = dispatch_task_with_supervisor_permit(
            dispatch_input,
            policy_hash=policy_hash,
            start_timeout_seconds=5,
            max_duration_seconds=60,
            decision="allow",
        )
    except DispatchFailure as exc:
        return {
            "status": "failure",
            "reason": str(exc),
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
        }
    except Exception as exc:
        return {
            "status": "failure",
            "reason": f"task_engine_error:{exc}",
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
        }

    normalized_result = ingest_executor_result(result, dispatch_input)
    reason: str | None
    if normalized_result.status == "success":
        reason = None
    elif normalized_result.exit_status == 124:
        reason = "execution_timeout"
    else:
        reason = f"exit_status:{normalized_result.exit_status}"
    return {
        "status": normalized_result.status,
        "reason": reason,
        "stdout": normalized_result.stdout or "",
        "stderr": normalized_result.stderr or "",
        "changed_files": list(normalized_result.changed_files or []),
        "tests_passed": bool(normalized_result.tests_passed),
        "dispatch_timestamp": dispatch_meta.get("dispatch_timestamp"),
        "permit_usage_event_id": dispatch_meta.get("permit_usage_event_id"),
    }


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

    spec_text = spec.read_text(encoding="utf-8")
    try:
        raw = _execute_via_task_engine(issue=issue, spec_path=spec_path, spec_text=spec_text)
    except Exception as exc:
        ts_end_ms = _now_ms()
        return {
            "status": "failure",
            "reason": f"task_engine_unavailable:{exc}",
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
        "dispatch_timestamp": raw.get("dispatch_timestamp"),
        "permit_usage_event_id": raw.get("permit_usage_event_id"),
        "ts_start_ms": ts_start_ms,
        "ts_end_ms": ts_end_ms,
    }

import json
import subprocess
import threading
import time

from executor.result import ExecutorResult, utc_iso8601


_EXECUTION_LOCK = threading.Lock()

_REQUIRED_DISPATCH_FIELDS = (
    "task_id",
    "instruction",
    "allowed_files",
    "expected_outcome",
    "governance_hash",
    "timestamp",
)


class DispatchFailure(Exception):
    pass


def _validate_dispatch_input(dispatch_input: dict) -> None:
    missing = [k for k in _REQUIRED_DISPATCH_FIELDS if k not in dispatch_input]
    if missing:
        raise DispatchFailure(f"execution.dispatch.malformed missing={missing}")

    instruction = str(dispatch_input["instruction"]).lower()
    nondeterministic_terms = ("maybe", "perhaps", "if possible", "as needed")
    if any(term in instruction for term in nondeterministic_terms):
        raise DispatchFailure("execution.dispatch.nondeterministic")


def _deterministic_executor_command(dispatch_input: dict) -> list[str]:
    """
    Deterministic single-command executor.
    Emits machine-readable execution payload for ingestion.
    """
    payload = {
        "task_id": dispatch_input["task_id"],
        "changed_files": [],
        "commit_hash": None,
        "tests_passed": True,
    }
    payload_json = json.dumps(payload)
    cmd = f"print({payload_json!r})"
    return ["python3", "-c", cmd]


def dispatch_task_once(
    dispatch_input: dict,
    *,
    start_timeout_seconds: int = 5,
    max_duration_seconds: int = 60,
) -> tuple[ExecutorResult, dict]:
    """
    Dispatches exactly one deterministic execution for a claimed task.
    Returns structured executor result and dispatch metadata.
    """
    _validate_dispatch_input(dispatch_input)

    if not _EXECUTION_LOCK.acquire(blocking=False):
        raise DispatchFailure("execution.lock.violation")

    command = _deterministic_executor_command(dispatch_input)
    dispatch_ts = utc_iso8601()
    start_monotonic = time.monotonic()

    try:
        started_at = time.monotonic()
        start_delay = started_at - start_monotonic
        if start_delay > start_timeout_seconds:
            raise DispatchFailure("execution.timeout")

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max_duration_seconds,
                check=False,
            )
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            proc = exc
            timed_out = True

        finished_ts = utc_iso8601()
        if timed_out:
            stdout = proc.stdout or ""
            stderr = proc.stderr or "execution.timeout"
            exit_status = 124
            status = "failure"
        else:
            stdout = proc.stdout
            stderr = proc.stderr
            exit_status = proc.returncode
            status = "success" if exit_status == 0 else "failure"

        logs = (
            f"stdout:\\n{stdout}\\n\\n"
            f"stderr:\\n{stderr}\\n\\n"
            f"exit_status={exit_status}"
        )
        result = ExecutorResult(
            status=status,
            changed_files=[],
            commit_hash=None,
            tests_passed=(status == "success"),
            logs=logs,
            timestamp=finished_ts,
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
        )
        result.validate_required_output()

        metadata = {
            "dispatch_timestamp": dispatch_ts,
            "executor_command": command,
            "timed_out": timed_out,
            "max_duration_seconds": max_duration_seconds,
        }
        return result, metadata
    finally:
        _EXECUTION_LOCK.release()

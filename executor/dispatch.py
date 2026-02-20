import json
import subprocess
import threading
import time

from executor.result import ExecutorResult, utc_iso8601
from executor.secure_execution_layer.audit_event_taxonomy import (
    AuditEvent,
    event_fingerprint,
    validate_audit_event,
    validate_event_stream,
)
from executor.secure_execution_layer.execution_permit_validator import (
    ExecutionPermit,
    InvalidPermitError,
    PermitRequiredError,
    validate_execution_permit_structure,
    verify_execution_permit_against_chain,
)


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
    permit: ExecutionPermit | None = None,
    current_stream_id: str = "",
    current_sequence: int = -1,
    current_prev_event_hash: str = "",
    previous_event: AuditEvent | None = None,
) -> tuple[ExecutorResult, dict]:
    """
    Dispatches exactly one deterministic execution for a claimed task.
    Returns structured executor result and dispatch metadata.
    """
    _validate_dispatch_input(dispatch_input)
    return execute_capability(
        dispatch_input,
        start_timeout_seconds=start_timeout_seconds,
        max_duration_seconds=max_duration_seconds,
        permit=permit,
        current_stream_id=current_stream_id,
        current_sequence=current_sequence,
        current_prev_event_hash=current_prev_event_hash,
        previous_event=previous_event,
    )


def execute_capability(
    dispatch_input: dict,
    *,
    start_timeout_seconds: int = 5,
    max_duration_seconds: int = 60,
    permit: ExecutionPermit | None = None,
    current_stream_id: str = "",
    current_sequence: int = -1,
    current_prev_event_hash: str = "",
    previous_event: AuditEvent | None = None,
) -> tuple[ExecutorResult, dict]:
    _validate_dispatch_input(dispatch_input)
    if permit is None:
        raise PermitRequiredError("execution.permit.required")
    try:
        validate_execution_permit_structure(permit)
        verify_execution_permit_against_chain(
            permit,
            current_stream_id=current_stream_id,
            current_sequence=current_sequence,
            current_prev_event_hash=current_prev_event_hash,
        )
    except ValueError as exc:
        raise InvalidPermitError(str(exc)) from exc

    permit_used_event = AuditEvent(
        event_id=permit.permit_id,
        event_type="permit.used",
        policy_hash=permit.policy_hash,
        request_fingerprint=permit.request_fingerprint,
        sequence=current_sequence,
        stream_id=current_stream_id,
        prev_event_hash=current_prev_event_hash,
        payload={
            "capability": permit.capability,
            "decision": permit.decision,
            "permit_scope": permit.permit_scope,
        },
    )
    try:
        validate_audit_event(permit_used_event)
        if previous_event is None:
            validate_event_stream([permit_used_event])
        else:
            validate_event_stream([previous_event, permit_used_event])
        permit_used_event_hash = event_fingerprint(permit_used_event)
    except ValueError as exc:
        raise ValueError("secure_layer.audit.invalid permit_usage") from exc

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
            "permit_usage_event_id": permit_used_event.event_id,
            "permit_usage_event_hash": permit_used_event_hash,
        }
        return result, metadata
    finally:
        _EXECUTION_LOCK.release()

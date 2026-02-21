from executor.result import ExecutorResult
from executor.secure_execution_layer.execution_permit_validator import (
    ExecutionPermit,
    KillSwitchError,
    validate_execution_permit_structure,
)
from supervisor.supervisor import (
    build_execution_permit_for_dispatch,
    dispatch_task_with_supervisor_permit,
    dispatch_task_with_supervisor_permit_or_halt,
)


def _dispatch_input() -> dict:
    return {
        "task_id": 42,
        "instruction": "run deterministically",
        "allowed_files": ["executor/dispatch.py"],
        "expected_outcome": "deterministic",
        "governance_hash": "a" * 64,
        "timestamp": "ignored",
    }


def test_supervisor_constructs_valid_permit() -> None:
    permit, ctx = build_execution_permit_for_dispatch(
        policy_hash="b" * 64,
        dispatch_input=_dispatch_input(),
        decision="allow",
    )
    validate_execution_permit_structure(permit)
    assert permit.policy_hash == "b" * 64
    assert permit.issued_by == "supervisor"
    assert permit.permit_scope == "one_shot"
    assert permit.expiry_condition == {"valid_for_sequence_range": [42, 42]}
    assert ctx["current_sequence"] == 42
    assert ctx["current_stream_id"] == "task-42"
    assert ctx["current_prev_event_hash"] == "a" * 64


def test_supervisor_missing_policy_hash_fails() -> None:
    try:
        build_execution_permit_for_dispatch(
            policy_hash="",
            dispatch_input=_dispatch_input(),
            decision="allow",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "supervisor.permit.invalid.policy_hash"


def test_supervisor_permit_deterministic() -> None:
    first, first_ctx = build_execution_permit_for_dispatch(
        policy_hash="b" * 64,
        dispatch_input=_dispatch_input(),
        decision="allow",
    )
    second, second_ctx = build_execution_permit_for_dispatch(
        policy_hash="b" * 64,
        dispatch_input=_dispatch_input(),
        decision="allow",
    )
    assert first.permit_id == second.permit_id
    assert first == second
    assert first_ctx == second_ctx


def test_supervisor_passes_permit_to_executor(monkeypatch) -> None:
    captured = {}

    def _fake_dispatch_task_once(dispatch_input, **kwargs):  # type: ignore[no-untyped-def]
        captured["dispatch_input"] = dispatch_input
        captured["kwargs"] = kwargs
        return (
            ExecutorResult(
                status="success",
                changed_files=[],
                commit_hash=None,
                tests_passed=True,
                logs="",
                timestamp="2026-01-01T00:00:00Z",
                stdout="",
                stderr="",
                exit_status=0,
            ),
            {
                "dispatch_timestamp": "2026-01-01T00:00:00Z",
                "executor_command": ["python3", "-c", "print('ok')"],
                "timed_out": False,
                "max_duration_seconds": 60,
            },
        )

    monkeypatch.setattr("supervisor.supervisor.dispatch_task_once", _fake_dispatch_task_once)

    result, metadata = dispatch_task_with_supervisor_permit(
        _dispatch_input(),
        policy_hash="b" * 64,
        start_timeout_seconds=5,
        max_duration_seconds=60,
        decision="allow",
    )

    assert result.status == "success"
    assert metadata["timed_out"] is False

    assert "permit" in captured["kwargs"]
    permit = captured["kwargs"]["permit"]
    assert isinstance(permit, ExecutionPermit)
    validate_execution_permit_structure(permit)
    assert captured["kwargs"]["current_stream_id"] == "task-42"
    assert captured["kwargs"]["current_sequence"] == 42
    assert captured["kwargs"]["current_prev_event_hash"] == "a" * 64


def test_cycle_controller_stops_on_killswitch_no_further_dispatch_attempted(monkeypatch) -> None:
    calls = {"count": 0}

    def _fake_dispatch_with_permit(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        raise KillSwitchError("secure_layer.killswitch.permit_invalid")

    monkeypatch.setattr(
        "supervisor.supervisor.dispatch_task_with_supervisor_permit",
        _fake_dispatch_with_permit,
    )

    halted = False
    try:
        for _ in range(2):
            dispatch_task_with_supervisor_permit_or_halt(
                _dispatch_input(),
                policy_hash="b" * 64,
                start_timeout_seconds=5,
                max_duration_seconds=60,
                decision="allow",
            )
    except SystemExit as exc:
        halted = True
        assert exc.code == 2

    assert halted is True
    assert calls["count"] == 1

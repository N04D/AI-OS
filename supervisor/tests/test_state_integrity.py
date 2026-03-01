from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest

from supervisor.state_integrity import DENY_STATE_INTEGRITY
from supervisor.state_integrity import StateIntegrityError
from supervisor.state_integrity import verify_state_integrity


def test_baseline_then_verify_ok(tmp_path: Path) -> None:
    autonomy_state = tmp_path / "autonomy_state.json"
    budget_state = tmp_path / "budgets.json"
    autonomy_state.write_text('{"INTERRUPT_FLAG":false}\n', encoding="utf-8")
    budget_state.write_text('{"version":"v0.1","timezone":"UTC","budgets":{}}\n', encoding="utf-8")

    metadata = tmp_path / "state_integrity.json"
    audit = tmp_path / "integrity_events.jsonl"
    now = datetime(2026, 2, 27, 14, 0, tzinfo=UTC)

    first = verify_state_integrity(
        targets={"autonomy_state": autonomy_state, "budget_state": budget_state},
        metadata_path=metadata,
        audit_path=audit,
        now_utc=now,
    )
    second = verify_state_integrity(
        targets={"autonomy_state": autonomy_state, "budget_state": budget_state},
        metadata_path=metadata,
        audit_path=audit,
        now_utc=now,
    )

    assert first["status"] == "baseline_recorded"
    assert second["status"] == "verified"


def test_manual_modification_is_denied(tmp_path: Path) -> None:
    autonomy_state = tmp_path / "autonomy_state.json"
    budget_state = tmp_path / "budgets.json"
    autonomy_state.write_text('{"INTERRUPT_FLAG":false}\n', encoding="utf-8")
    budget_state.write_text('{"version":"v0.1","timezone":"UTC","budgets":{}}\n', encoding="utf-8")

    metadata = tmp_path / "state_integrity.json"
    audit = tmp_path / "integrity_events.jsonl"

    verify_state_integrity(
        targets={"autonomy_state": autonomy_state, "budget_state": budget_state},
        metadata_path=metadata,
        audit_path=audit,
    )

    budget_state.write_text('{"version":"v0.1","timezone":"UTC","budgets":{"x":1}}\n', encoding="utf-8")
    with pytest.raises(StateIntegrityError) as exc:
        verify_state_integrity(
            targets={"autonomy_state": autonomy_state, "budget_state": budget_state},
            metadata_path=metadata,
            audit_path=audit,
        )

    assert exc.value.reason_code == DENY_STATE_INTEGRITY
    assert "integrity_mismatch:budget_state" in str(exc.value)

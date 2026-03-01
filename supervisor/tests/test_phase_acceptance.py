from __future__ import annotations

import json
from pathlib import Path

import pytest

from supervisor.phase_acceptance import PhaseAcceptanceError
from supervisor.phase_acceptance import verify_phase_acceptance_evidence


def _valid_evidence() -> dict:
    return {
        "version": "v0.1",
        "pytest": {
            "passed": 377,
            "failed": 0,
            "skipped": 2,
            "skip_justifications": [
                "env: external integration unavailable",
                "env: policy fixture not present",
            ],
        },
        "roadmap_updated": True,
        "progress_updated": True,
        "halt_entered": True,
    }


def test_phase_acceptance_positive_case() -> None:
    result = verify_phase_acceptance_evidence(_valid_evidence())
    assert result["status"] == "ok"
    assert result["pytest"]["failed"] == 0


def test_phase_acceptance_rejects_failed_pytest() -> None:
    payload = _valid_evidence()
    payload["pytest"]["failed"] = 1
    with pytest.raises(PhaseAcceptanceError) as exc:
        verify_phase_acceptance_evidence(payload)
    assert exc.value.reason_code == "DENY_PHASE_ACCEPTANCE_PYTEST_FAILED"


def test_phase_acceptance_rejects_missing_halt() -> None:
    payload = _valid_evidence()
    payload["halt_entered"] = False
    with pytest.raises(PhaseAcceptanceError) as exc:
        verify_phase_acceptance_evidence(payload)
    assert exc.value.reason_code == "DENY_PHASE_ACCEPTANCE_HALT_MISSING"


def test_phase_acceptance_rejects_unjustified_skips() -> None:
    payload = _valid_evidence()
    payload["pytest"]["skipped"] = 2
    payload["pytest"]["skip_justifications"] = ["only one reason"]
    with pytest.raises(PhaseAcceptanceError) as exc:
        verify_phase_acceptance_evidence(payload)
    assert exc.value.reason_code == "DENY_PHASE_ACCEPTANCE_SKIP_JUSTIFICATION_MISSING"


def test_phase_acceptance_rejects_missing_progress_update() -> None:
    payload = _valid_evidence()
    payload["progress_updated"] = False
    with pytest.raises(PhaseAcceptanceError) as exc:
        verify_phase_acceptance_evidence(payload)
    assert exc.value.reason_code == "DENY_PHASE_ACCEPTANCE_PROGRESS_MISSING"


def test_phase_acceptance_fixture_file_roundtrip(tmp_path: Path) -> None:
    payload = _valid_evidence()
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
    result = verify_phase_acceptance_evidence(loaded)
    assert result["status"] == "ok"

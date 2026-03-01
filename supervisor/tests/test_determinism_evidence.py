from __future__ import annotations

import ast
import inspect

import pytest

import supervisor.determinism_evidence as determinism_evidence
from supervisor.determinism_evidence import DeterminismEvidenceError
from supervisor.determinism_evidence import verify_determinism_evidence


def _hex64(char: str) -> str:
    return char * 64


def test_determinism_evidence_accepts_valid_med_payload() -> None:
    payload = {
        "version": "v0.1",
        "risk_tier": "MED",
        "input_fingerprint": _hex64("a"),
        "output_fingerprint": _hex64("b"),
        "rerun_consistent": True,
        "timestamps_controlled": True,
        "artifacts": ["artifacts/determinism_evidence.json"],
    }
    result = verify_determinism_evidence(payload)
    assert result["status"] == "ok"


def test_determinism_evidence_rejects_missing_med_requirements() -> None:
    payload = {
        "version": "v0.1",
        "risk_tier": "MED",
        "input_fingerprint": _hex64("a"),
        "output_fingerprint": _hex64("b"),
        "rerun_consistent": False,
        "timestamps_controlled": True,
        "artifacts": ["artifacts/determinism_evidence.json"],
    }
    with pytest.raises(DeterminismEvidenceError) as exc:
        verify_determinism_evidence(payload)
    assert exc.value.reason_code == "DENY_DETERMINISM_EVIDENCE_INCOMPLETE"


def test_determinism_evidence_rejects_schema_errors() -> None:
    payload = {
        "version": "v0.1",
        "risk_tier": "LOW",
        "input_fingerprint": "bad",
        "output_fingerprint": _hex64("b"),
        "rerun_consistent": True,
        "timestamps_controlled": True,
        "artifacts": ["a"],
    }
    with pytest.raises(DeterminismEvidenceError) as exc:
        verify_determinism_evidence(payload)
    assert exc.value.reason_code == "DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID"


def test_determinism_evidence_is_deterministic_for_identical_input() -> None:
    payload = {
        "version": "v0.1",
        "risk_tier": "MED",
        "input_fingerprint": _hex64("c"),
        "output_fingerprint": _hex64("d"),
        "rerun_consistent": True,
        "timestamps_controlled": True,
        "artifacts": ["artifacts/a.json", "artifacts/b.json"],
    }
    first = verify_determinism_evidence(payload)
    second = verify_determinism_evidence(payload)
    assert first == second


def test_determinism_evidence_rejects_uncontrolled_timestamp_field() -> None:
    payload = {
        "version": "v0.1",
        "risk_tier": "LOW",
        "input_fingerprint": _hex64("a"),
        "output_fingerprint": _hex64("b"),
        "rerun_consistent": True,
        "timestamps_controlled": True,
        "artifacts": ["artifacts/determinism_evidence.json"],
        "created_at": "2026-02-27T00:00:00Z",
    }
    with pytest.raises(DeterminismEvidenceError) as exc:
        verify_determinism_evidence(payload)
    assert exc.value.reason_code == "DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID"


def test_determinism_evidence_rejects_high_without_rerun_consistency() -> None:
    payload = {
        "version": "v0.1",
        "risk_tier": "HIGH",
        "input_fingerprint": _hex64("a"),
        "output_fingerprint": _hex64("b"),
        "rerun_consistent": False,
        "timestamps_controlled": True,
        "artifacts": ["artifacts/determinism_evidence.json"],
    }
    with pytest.raises(DeterminismEvidenceError) as exc:
        verify_determinism_evidence(payload)
    assert exc.value.reason_code == "DENY_DETERMINISM_EVIDENCE_INCOMPLETE"


def test_determinism_verifier_has_no_wall_clock_imports() -> None:
    tree = ast.parse(inspect.getsource(determinism_evidence))
    banned = {"datetime", "time"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = {alias.name.split(".")[0] for alias in node.names}
            assert not (imported & banned)
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            assert top not in banned

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID = "DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID"
DENY_PHASE_ACCEPTANCE_PYTEST_FAILED = "DENY_PHASE_ACCEPTANCE_PYTEST_FAILED"
DENY_PHASE_ACCEPTANCE_ROADMAP_MISSING = "DENY_PHASE_ACCEPTANCE_ROADMAP_MISSING"
DENY_PHASE_ACCEPTANCE_PROGRESS_MISSING = "DENY_PHASE_ACCEPTANCE_PROGRESS_MISSING"
DENY_PHASE_ACCEPTANCE_HALT_MISSING = "DENY_PHASE_ACCEPTANCE_HALT_MISSING"
DENY_PHASE_ACCEPTANCE_SKIP_JUSTIFICATION_MISSING = "DENY_PHASE_ACCEPTANCE_SKIP_JUSTIFICATION_MISSING"


class PhaseAcceptanceError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, f"{field} must be bool")
    return value


def _require_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, f"{field} must be int >= 0")
    return value


def load_phase_acceptance_evidence(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, f"missing evidence file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, f"invalid evidence json: {path}") from exc
    if not isinstance(payload, dict):
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, "evidence must be object")
    return payload


def verify_phase_acceptance_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "pytest",
        "roadmap_updated",
        "progress_updated",
        "halt_entered",
    }
    if set(evidence.keys()) != required:
        raise PhaseAcceptanceError(
            DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID,
            f"evidence keys must be exactly {sorted(required)}",
        )

    version = evidence.get("version")
    if version != "v0.1":
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, "version must be v0.1")

    pytest_section = evidence.get("pytest")
    if not isinstance(pytest_section, dict):
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID, "pytest must be object")
    if set(pytest_section.keys()) != {"passed", "failed", "skipped", "skip_justifications"}:
        raise PhaseAcceptanceError(
            DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID,
            "pytest keys must be exactly passed,failed,skipped,skip_justifications",
        )

    passed = _require_int(pytest_section.get("passed"), "pytest.passed")
    failed = _require_int(pytest_section.get("failed"), "pytest.failed")
    skipped = _require_int(pytest_section.get("skipped"), "pytest.skipped")
    justifications = pytest_section.get("skip_justifications")
    if not isinstance(justifications, list) or any(not isinstance(item, str) or not item.strip() for item in justifications):
        raise PhaseAcceptanceError(
            DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID,
            "pytest.skip_justifications must be list[str] with non-empty items",
        )

    if failed != 0:
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_PYTEST_FAILED, f"pytest failed={failed}")
    if skipped > 0 and len(justifications) != skipped:
        raise PhaseAcceptanceError(
            DENY_PHASE_ACCEPTANCE_SKIP_JUSTIFICATION_MISSING,
            f"skipped={skipped} requires equal number of justifications",
        )
    if not _require_bool(evidence.get("roadmap_updated"), "roadmap_updated"):
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_ROADMAP_MISSING, "roadmap update required")
    if not _require_bool(evidence.get("progress_updated"), "progress_updated"):
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_PROGRESS_MISSING, "progress update required")
    if not _require_bool(evidence.get("halt_entered"), "halt_entered"):
        raise PhaseAcceptanceError(DENY_PHASE_ACCEPTANCE_HALT_MISSING, "HALT entry required")

    return {
        "status": "ok",
        "pytest": {"passed": passed, "failed": failed, "skipped": skipped},
        "roadmap_updated": True,
        "progress_updated": True,
        "halt_entered": True,
    }

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID = "DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID"
DENY_DETERMINISM_EVIDENCE_INCOMPLETE = "DENY_DETERMINISM_EVIDENCE_INCOMPLETE"


class DeterminismEvidenceError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def load_determinism_evidence(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, f"missing evidence file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, f"invalid evidence json: {path}") from exc
    if not isinstance(payload, dict):
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, "evidence must be object")
    return payload


def verify_determinism_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "risk_tier",
        "input_fingerprint",
        "output_fingerprint",
        "rerun_consistent",
        "timestamps_controlled",
        "artifacts",
    }
    if set(payload.keys()) != required:
        raise DeterminismEvidenceError(
            DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID,
            f"evidence keys must be exactly {sorted(required)}",
        )

    if payload.get("version") != "v0.1":
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, "version must be v0.1")

    risk_tier = payload.get("risk_tier")
    if risk_tier not in {"LOW", "MED", "HIGH"}:
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, "risk_tier must be LOW|MED|HIGH")

    for field in ("input_fingerprint", "output_fingerprint"):
        value = payload.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, f"{field} must be sha256 hex")

    rerun_consistent = payload.get("rerun_consistent")
    timestamps_controlled = payload.get("timestamps_controlled")
    if not isinstance(rerun_consistent, bool):
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, "rerun_consistent must be bool")
    if not isinstance(timestamps_controlled, bool):
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, "timestamps_controlled must be bool")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or any(not isinstance(item, str) or not item.strip() for item in artifacts):
        raise DeterminismEvidenceError(
            DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID,
            "artifacts must be list[str] with non-empty values",
        )
    if not artifacts:
        raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID, "artifacts must not be empty")

    if risk_tier in {"MED", "HIGH"}:
        if not rerun_consistent:
            raise DeterminismEvidenceError(DENY_DETERMINISM_EVIDENCE_INCOMPLETE, "MED/HIGH requires rerun_consistent=true")
        if not timestamps_controlled:
            raise DeterminismEvidenceError(
                DENY_DETERMINISM_EVIDENCE_INCOMPLETE,
                "MED/HIGH requires timestamps_controlled=true",
            )

    return {
        "status": "ok",
        "risk_tier": risk_tier,
        "rerun_consistent": rerun_consistent,
        "timestamps_controlled": timestamps_controlled,
        "artifacts": list(artifacts),
    }

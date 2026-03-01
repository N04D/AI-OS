from __future__ import annotations

import hashlib
import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_INTEGRITY_METADATA_PATH = Path("state/supervisor/state_integrity.json")
DEFAULT_INTEGRITY_AUDIT_LOG_PATH = Path("logs/control/integrity_events.jsonl")

DENY_STATE_INTEGRITY = "DENY_STATE_INTEGRITY"


class StateIntegrityError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _utc_iso(ts: datetime | None = None) -> str:
    value = ts or datetime.now(UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise StateIntegrityError(DENY_STATE_INTEGRITY, f"missing_state_file:{path}")
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_hashes(targets: dict[str, Path]) -> dict[str, str]:
    if not isinstance(targets, dict) or not targets:
        raise StateIntegrityError(DENY_STATE_INTEGRITY, "integrity targets must be non-empty object")
    return {key: _sha256_file(Path(path)) for key, path in sorted(targets.items())}


def _audit(
    *,
    audit_path: Path,
    decision: str,
    reason_code: str,
    hashes: dict[str, str],
    detail: str = "",
    now_utc: datetime | None = None,
) -> None:
    record = {
        "ts_utc": _utc_iso(now_utc),
        "decision": decision,
        "reason_code": reason_code,
        "detail": detail,
        "hashes": {k: hashes[k] for k in sorted(hashes.keys())},
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical_json(record) + "\n")


def _load_metadata(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateIntegrityError(DENY_STATE_INTEGRITY, f"invalid_integrity_metadata_json:{path}") from exc
    if not isinstance(payload, dict):
        raise StateIntegrityError(DENY_STATE_INTEGRITY, "integrity metadata must be object")
    if payload.get("version") != "v0.1":
        raise StateIntegrityError(DENY_STATE_INTEGRITY, "integrity metadata version must be v0.1")
    files = payload.get("files")
    if not isinstance(files, dict):
        raise StateIntegrityError(DENY_STATE_INTEGRITY, "integrity metadata files must be object")
    normalized: dict[str, str] = {}
    for key, value in files.items():
        if not isinstance(key, str) or not key:
            raise StateIntegrityError(DENY_STATE_INTEGRITY, "integrity metadata key invalid")
        if not isinstance(value, str) or len(value) != 64:
            raise StateIntegrityError(DENY_STATE_INTEGRITY, f"integrity metadata hash invalid:{key}")
        normalized[key] = value
    return {k: normalized[k] for k in sorted(normalized.keys())}


def _save_metadata(path: Path, hashes: dict[str, str]) -> None:
    payload = {"version": "v0.1", "files": {k: hashes[k] for k in sorted(hashes.keys())}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(payload) + "\n", encoding="utf-8")


def verify_state_integrity(
    *,
    targets: dict[str, Path],
    metadata_path: Path = DEFAULT_INTEGRITY_METADATA_PATH,
    audit_path: Path = DEFAULT_INTEGRITY_AUDIT_LOG_PATH,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    current_hashes = _current_hashes(targets)
    expected_hashes = _load_metadata(metadata_path)
    if expected_hashes is None:
        _save_metadata(metadata_path, current_hashes)
        _audit(
            audit_path=audit_path,
            decision="allow",
            reason_code="INTEGRITY_BASELINE_RECORDED",
            hashes=current_hashes,
            now_utc=now_utc,
        )
        return {"status": "baseline_recorded", "hashes": current_hashes}

    if set(expected_hashes.keys()) != set(current_hashes.keys()):
        _audit(
            audit_path=audit_path,
            decision="deny",
            reason_code=DENY_STATE_INTEGRITY,
            hashes=current_hashes,
            detail="integrity target set mismatch",
            now_utc=now_utc,
        )
        raise StateIntegrityError(DENY_STATE_INTEGRITY, "integrity target set mismatch")

    for key in sorted(current_hashes.keys()):
        if current_hashes[key] != expected_hashes[key]:
            _audit(
                audit_path=audit_path,
                decision="deny",
                reason_code=DENY_STATE_INTEGRITY,
                hashes=current_hashes,
                detail=f"integrity_mismatch:{key}",
                now_utc=now_utc,
            )
            raise StateIntegrityError(DENY_STATE_INTEGRITY, f"integrity_mismatch:{key}")

    _audit(
        audit_path=audit_path,
        decision="allow",
        reason_code="INTEGRITY_VERIFIED",
        hashes=current_hashes,
        now_utc=now_utc,
    )
    return {"status": "verified", "hashes": current_hashes}


def update_state_integrity_reference(
    *,
    targets: dict[str, Path],
    metadata_path: Path = DEFAULT_INTEGRITY_METADATA_PATH,
    audit_path: Path = DEFAULT_INTEGRITY_AUDIT_LOG_PATH,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    current_hashes = _current_hashes(targets)
    _save_metadata(metadata_path, current_hashes)
    _audit(
        audit_path=audit_path,
        decision="allow",
        reason_code="INTEGRITY_REFERENCE_UPDATED",
        hashes=current_hashes,
        now_utc=now_utc,
    )
    return {"status": "reference_updated", "hashes": current_hashes}

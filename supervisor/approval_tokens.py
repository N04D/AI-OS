from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_TOKEN_STATE_PATH = Path("state/supervisor/approval_tokens.json")
DEFAULT_AUDIT_LOG_PATH = Path("logs/control/approval_token_audit.jsonl")

DENY_TOKEN_MISSING = "DENY_TOKEN_MISSING"
DENY_TOKEN_SCHEMA_INVALID = "DENY_TOKEN_SCHEMA_INVALID"
DENY_TOKEN_BAD_SIG = "DENY_TOKEN_BAD_SIG"
DENY_TOKEN_EXPIRED = "DENY_TOKEN_EXPIRED"
DENY_TOKEN_SCOPE_INVALID = "DENY_TOKEN_SCOPE_INVALID"
DENY_TOKEN_REUSED = "DENY_TOKEN_REUSED"


class ApprovalTokenError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_iso(ts: datetime | None = None) -> str:
    value = ts or _utc_now()
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _urlsafe_b64_decode(raw: str) -> bytes:
    pad_len = (-len(raw)) % 4
    padded = raw + ("=" * pad_len)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": "v0.1", "used_hashes": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, f"invalid token state json: {path}") from exc
    if not isinstance(payload, dict):
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token state must be object")
    if payload.get("version") != "v0.1":
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token state version must be v0.1")
    used_hashes = payload.get("used_hashes")
    if not isinstance(used_hashes, dict):
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token state used_hashes must be object")
    normalized: dict[str, int] = {}
    for token_sha, exp in used_hashes.items():
        if not isinstance(token_sha, str) or len(token_sha) != 64:
            raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token hash key invalid")
        if not isinstance(exp, int):
            raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token exp invalid")
        normalized[token_sha] = exp
    return {"version": "v0.1", "used_hashes": normalized}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(state) + "\n", encoding="utf-8")


def _audit(
    *,
    audit_path: Path,
    token_sha256: str,
    scope: str,
    operation: str,
    decision: str,
    reason_code: str,
    now_utc: datetime,
) -> None:
    record = {
        "ts_utc": _utc_iso(now_utc),
        "scope": scope,
        "operation": operation,
        "token_sha256": token_sha256,
        "decision": decision,
        "reason_code": reason_code,
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical_json(record) + "\n")


def _parse_token_payload(token: str) -> dict[str, Any]:
    if "." not in token:
        parsed = json.loads(token)
        if not isinstance(parsed, dict):
            raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "json token must be an object")
        return parsed

    payload_b64, sig_b64 = token.split(".", 1)
    secret = (os.environ.get("APPROVAL_SECRET", "") or "").strip()
    if not secret:
        raise ApprovalTokenError(DENY_TOKEN_BAD_SIG, "APPROVAL_SECRET missing for signed token")
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    provided = _urlsafe_b64_decode(sig_b64)
    if not hmac.compare_digest(expected, provided):
        raise ApprovalTokenError(DENY_TOKEN_BAD_SIG, "signed token signature mismatch")
    try:
        payload_raw = _urlsafe_b64_decode(payload_b64).decode("utf-8")
        parsed = json.loads(payload_raw)
    except Exception as exc:
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "signed token payload invalid") from exc
    if not isinstance(parsed, dict):
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "signed token payload must be object")
    return parsed


def require_approval_token(
    *,
    scope: str,
    operation: str,
    token: str | None = None,
    now_utc: datetime | None = None,
    state_path: Path = DEFAULT_TOKEN_STATE_PATH,
    audit_path: Path = DEFAULT_AUDIT_LOG_PATH,
) -> dict[str, Any]:
    now = (now_utc or _utc_now()).astimezone(UTC)
    raw_token = (token if token is not None else os.environ.get("SUPERVISOR_APPROVAL_TOKEN", "")).strip()
    token_sha = _token_hash(raw_token) if raw_token else "0" * 64
    if not raw_token:
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=DENY_TOKEN_MISSING,
            now_utc=now,
        )
        raise ApprovalTokenError(DENY_TOKEN_MISSING, "approval token required")

    try:
        payload = _parse_token_payload(raw_token)
    except ApprovalTokenError as exc:
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=exc.reason_code,
            now_utc=now,
        )
        raise
    except Exception as exc:
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=DENY_TOKEN_SCHEMA_INVALID,
            now_utc=now,
        )
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token parse failure") from exc

    required = {"v", "scope", "exp", "jti"}
    if set(payload.keys()) != required:
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=DENY_TOKEN_SCHEMA_INVALID,
            now_utc=now,
        )
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token keys must be exactly v,scope,exp,jti")

    token_scope = payload.get("scope")
    token_exp = payload.get("exp")
    token_jti = payload.get("jti")
    token_version = payload.get("v")
    if token_version != 1:
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "token version must be 1")
    if not isinstance(token_scope, list) or any(not isinstance(item, str) or not item for item in token_scope):
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "scope must be non-empty list[str]")
    if not isinstance(token_exp, int):
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "exp must be int")
    if not isinstance(token_jti, str) or len(token_jti) < 8:
        raise ApprovalTokenError(DENY_TOKEN_SCHEMA_INVALID, "jti invalid")

    if scope not in token_scope:
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=DENY_TOKEN_SCOPE_INVALID,
            now_utc=now,
        )
        raise ApprovalTokenError(DENY_TOKEN_SCOPE_INVALID, f"scope {scope} missing from token")

    if token_exp <= int(now.timestamp()):
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=DENY_TOKEN_EXPIRED,
            now_utc=now,
        )
        raise ApprovalTokenError(DENY_TOKEN_EXPIRED, "token expired")

    state = _load_state(state_path)
    used_hashes = dict(state.get("used_hashes", {}))
    now_s = int(now.timestamp())
    used_hashes = {key: value for key, value in used_hashes.items() if int(value) > now_s}
    if token_sha in used_hashes:
        _audit(
            audit_path=audit_path,
            token_sha256=token_sha,
            scope=scope,
            operation=operation,
            decision="denied",
            reason_code=DENY_TOKEN_REUSED,
            now_utc=now,
        )
        _save_state(state_path, {"version": "v0.1", "used_hashes": dict(sorted(used_hashes.items()))})
        raise ApprovalTokenError(DENY_TOKEN_REUSED, "token already used")

    used_hashes[token_sha] = int(token_exp)
    _save_state(state_path, {"version": "v0.1", "used_hashes": dict(sorted(used_hashes.items()))})
    _audit(
        audit_path=audit_path,
        token_sha256=token_sha,
        scope=scope,
        operation=operation,
        decision="allowed",
        reason_code="ALLOW",
        now_utc=now,
    )
    return {
        "scope": list(token_scope),
        "exp": int(token_exp),
        "jti": token_jti,
        "token_sha256": token_sha,
    }

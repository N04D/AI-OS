from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import pytest

from supervisor.approval_tokens import ApprovalTokenError
from supervisor.approval_tokens import require_approval_token


def _token(*, scopes: list[str], exp: int, jti: str = "token-jti-001") -> str:
    return json.dumps({"v": 1, "scope": scopes, "exp": exp, "jti": jti}, sort_keys=True)


def test_missing_token_denied_and_audited(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    audit_path = tmp_path / "audit.jsonl"
    now = datetime(2026, 2, 27, 14, 0, tzinfo=UTC)

    with pytest.raises(ApprovalTokenError) as exc:
        require_approval_token(
            scope="phase_start",
            operation="phase_start:Phase 3",
            token="",
            now_utc=now,
            state_path=state_path,
            audit_path=audit_path,
        )

    assert exc.value.reason_code == "DENY_TOKEN_MISSING"
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[-1]["decision"] == "denied"
    assert rows[-1]["reason_code"] == "DENY_TOKEN_MISSING"
    assert rows[-1]["token_sha256"] != ""


def test_expired_token_denied(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    audit_path = tmp_path / "audit.jsonl"
    now = datetime(2026, 2, 27, 14, 0, tzinfo=UTC)
    token = _token(scopes=["phase_start"], exp=int((now - timedelta(seconds=1)).timestamp()))

    with pytest.raises(ApprovalTokenError) as exc:
        require_approval_token(
            scope="phase_start",
            operation="phase_start:Phase 3",
            token=token,
            now_utc=now,
            state_path=state_path,
            audit_path=audit_path,
        )

    assert exc.value.reason_code == "DENY_TOKEN_EXPIRED"


def test_token_reuse_rejected_deterministically(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    audit_path = tmp_path / "audit.jsonl"
    now = datetime(2026, 2, 27, 14, 0, tzinfo=UTC)
    token = _token(scopes=["high_risk_autonomy"], exp=int((now + timedelta(minutes=10)).timestamp()))

    first = require_approval_token(
        scope="high_risk_autonomy",
        operation="dispatch_task:123",
        token=token,
        now_utc=now,
        state_path=state_path,
        audit_path=audit_path,
    )
    assert first["token_sha256"]

    with pytest.raises(ApprovalTokenError) as exc:
        require_approval_token(
            scope="high_risk_autonomy",
            operation="dispatch_task:123",
            token=token,
            now_utc=now,
            state_path=state_path,
            audit_path=audit_path,
        )
    assert exc.value.reason_code == "DENY_TOKEN_REUSED"

    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["decision"] == "allowed"
    assert rows[1]["decision"] == "denied"
    assert rows[1]["reason_code"] == "DENY_TOKEN_REUSED"
    assert rows[0]["token_sha256"] == rows[1]["token_sha256"]

from __future__ import annotations

import io
import json
import subprocess
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from supervisor import cli


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init")


def test_apply_revoke_requires_approval_and_updates_ledger_deterministically(tmp_path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)

    ledger_path = repo / "state" / "supervisor_capabilities.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(
            {
                "high_risk_pr_merge": {
                    "earned_at": "2026-02-01T00:00:00Z",
                    "granted": True,
                    "granted_at": "2026-02-02T00:00:00Z",
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "state/supervisor_capabilities.json")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "add ledger")

    baseline = _git(repo, "rev-parse", "HEAD")
    revoke_id = str(uuid.uuid4())

    request_path = repo / "requests" / "capabilities" / "revoke" / "20260225T000000Z__high_risk_pr_merge__security.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "revoke_id": revoke_id,
                "supervisor_id": "core",
                "capability": "high_risk_pr_merge",
                "revoked_at": "2026-02-25T00:00:00Z",
                "justification": "security incident requires immediate revocation",
                "baseline_commit": baseline,
                "policy_sha": "abc123",
                "status": "requested",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    approval_path = repo / "approvals" / "capabilities" / "revoke" / f"{revoke_id}.approved"
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(
        json.dumps(
            {
                "revoke_id": revoke_id,
                "approved_by": "human.reviewer",
                "approved_at": "2026-02-25T00:05:00Z",
                "decision": "approve",
                "signature_type": "human",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)
    code = cli.main(
        [
            "autonomy",
            "apply-revoke",
            "--request",
            str(request_path),
            "--approval",
            str(approval_path),
        ]
    )
    assert code == 0

    updated = json.loads(ledger_path.read_text(encoding="utf-8"))["high_risk_pr_merge"]
    assert updated["granted"] is False
    assert updated["earned_at"] == "2026-02-01T00:00:00Z"
    assert updated["granted_at"] == "2026-02-02T00:00:00Z"
    assert updated["revoked_at"] == "2026-02-25T00:00:00Z"
    assert updated["revoked_by"] == "human.reviewer"
    assert updated["source_revoke_id"] == revoke_id

    assert _git(repo, "log", "-1", "--pretty=%s") == f"chore(capabilities): revoke high_risk_pr_merge via {revoke_id}"


def test_apply_revoke_baseline_mismatch_returns_deterministic_reason(tmp_path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)

    revoke_id = str(uuid.uuid4())
    request_path = repo / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "revoke_id": revoke_id,
                "supervisor_id": "core",
                "capability": "high_risk_pr_merge",
                "revoked_at": "2026-02-25T00:00:00Z",
                "justification": "security incident requires immediate revocation",
                "baseline_commit": "deadbeef",
                "policy_sha": "abc123",
                "status": "requested",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    approval_path = repo / "approval.approved"
    approval_path.write_text(
        json.dumps(
            {
                "revoke_id": revoke_id,
                "approved_by": "human.reviewer",
                "approved_at": "2026-02-25T00:05:00Z",
                "decision": "approve",
                "signature_type": "human",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
            [
                "--json",
                "autonomy",
                "apply-revoke",
                "--request",
                str(request_path),
                "--approval",
                str(approval_path),
            ]
        )

    assert code == 1
    payload = json.loads(buf.getvalue().strip())
    assert payload["status"] == "error"
    assert payload["reason"].startswith("DENY_CAPABILITY_REVOKE_BASELINE_MISMATCH")


def test_apply_revoke_requires_approval_marker(tmp_path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)

    revoke_id = str(uuid.uuid4())
    baseline = _git(repo, "rev-parse", "HEAD")
    request_path = repo / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "revoke_id": revoke_id,
                "supervisor_id": "core",
                "capability": "high_risk_pr_merge",
                "revoked_at": "2026-02-25T00:00:00Z",
                "justification": "security incident requires immediate revocation",
                "baseline_commit": baseline,
                "policy_sha": "abc123",
                "status": "requested",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    missing_approval = repo / "missing.approved"
    monkeypatch.chdir(repo)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
            [
                "--json",
                "autonomy",
                "apply-revoke",
                "--request",
                str(request_path),
                "--approval",
                str(missing_approval),
            ]
        )

    assert code == 1
    payload = json.loads(buf.getvalue().strip())
    assert payload["reason"].startswith("DENY_CAPABILITY_REVOKE_INVALID")

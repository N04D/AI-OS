from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from supervisor.autonomy_capabilities import CapabilityActivationError
from supervisor.autonomy_capabilities import activate_capability


def _git(repo: Path, args: list[str]) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _init_repo_with_registry(entry: dict) -> Path:
    tmp = Path(tempfile.mkdtemp())
    _git(tmp, ["init"])
    (tmp / ".gitignore").write_text("logs/\n", encoding="utf-8")
    _write_json(tmp / "state/supervisor_capabilities.json", {"email.send": entry, "scheduler_guarded_skill_run": True})
    _git(tmp, ["add", ".gitignore", "state/supervisor_capabilities.json"])
    _git(
        tmp,
        [
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "baseline",
        ],
    )
    return tmp


def _email_env() -> dict[str, str]:
    return {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "u",
        "SMTP_PASS": "p",
        "SMTP_FROM": "from@example.com",
        "NETWORK_ACCESS_ENABLED": "true",
    }


def test_activate_capability_success_commits_and_audits() -> None:
    repo = _init_repo_with_registry(
        {
            "state": "IMPLEMENTED_NOT_ACTIVE",
            "granted": False,
            "proposal_issue": 60,
            "approved_by": "Don",
            "activated_by": None,
            "timestamps": {},
        }
    )
    result = activate_capability(repo, "email.send", env=_email_env())
    assert result["status"] == "ok"
    assert result["state"] == "ACTIVE"
    assert result["granted"] is True
    assert result["activated_by"] == "Don"

    ledger = json.loads((repo / "state/supervisor_capabilities.json").read_text(encoding="utf-8"))
    assert ledger["email.send"]["state"] == "ACTIVE"
    assert ledger["email.send"]["granted"] is True
    assert ledger["email.send"]["activated_by"] == "Don"
    assert "IMPLEMENTED_NOT_ACTIVE->ACTIVE" in ledger["email.send"]["timestamps"]

    audit_lines = (repo / "logs/control/capability_activation.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(audit_lines) == 1
    audit = json.loads(audit_lines[0])
    assert audit["capability"] == "email.send"
    assert audit["state_after"] == "ACTIVE"
    assert audit["activated_by"] == "Don"
    assert _git(repo, ["log", "-1", "--pretty=%s"]) == "chore(capabilities): activate email.send"
    assert _git(repo, ["status", "--short"]) == ""
    committed_files = [line for line in _git(repo, ["show", "--name-only", "--pretty=format:", "HEAD"]).splitlines() if line]
    assert committed_files == ["state/supervisor_capabilities.json"]


def test_activate_capability_fails_closed_when_prereq_missing() -> None:
    repo = _init_repo_with_registry(
        {
            "state": "IMPLEMENTED_NOT_ACTIVE",
            "granted": False,
            "proposal_issue": 60,
            "approved_by": "Don",
            "activated_by": None,
            "timestamps": {},
        }
    )
    head_before = _git(repo, ["rev-parse", "HEAD"])
    ledger_before = (repo / "state/supervisor_capabilities.json").read_text(encoding="utf-8")
    with pytest.raises(CapabilityActivationError) as exc:
        bad_env = _email_env()
        bad_env["SMTP_PASS"] = ""
        activate_capability(repo, "email.send", env=bad_env)
    assert exc.value.reason_code == "DENY_CAPABILITY_SECRETS_MISSING"
    assert (repo / "state/supervisor_capabilities.json").read_text(encoding="utf-8") == ledger_before
    assert _git(repo, ["rev-parse", "HEAD"]) == head_before
    assert not (repo / "logs/control/capability_activation.jsonl").exists()


def test_activate_capability_fails_when_approved_by_mismatch() -> None:
    repo = _init_repo_with_registry(
        {
            "state": "IMPLEMENTED_NOT_ACTIVE",
            "granted": False,
            "proposal_issue": 60,
            "approved_by": "Alice",
            "activated_by": None,
            "timestamps": {},
        }
    )
    with pytest.raises(CapabilityActivationError) as exc:
        activate_capability(repo, "email.send", env=_email_env())
    assert exc.value.reason_code == "DENY_CAPABILITY_APPROVAL_INVALID"

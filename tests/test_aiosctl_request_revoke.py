from __future__ import annotations

import json
import subprocess
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


def test_request_revoke_writes_artifact_and_commits_without_ledger_mutation(tmp_path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    baseline = _git(repo, "rev-parse", "HEAD")

    ledger = repo / "state" / "supervisor_capabilities.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps({"high_risk_pr_merge": {"granted": True, "granted_at": "2026-02-01T00:00:00Z"}}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)
    code = cli.main(
        [
            "autonomy",
            "request-revoke",
            "--cap",
            "high_risk_pr_merge",
            "--why",
            "security incident requires immediate revocation",
        ]
    )
    assert code == 0

    files = sorted((repo / "requests" / "capabilities" / "revoke").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))

    assert payload["status"] == "requested"
    assert payload["supervisor_id"] == "core"
    assert payload["capability"] == "high_risk_pr_merge"
    assert payload["baseline_commit"] == baseline
    assert len(payload["justification"]) >= 20
    assert payload["policy_sha"]

    assert json.loads(ledger.read_text(encoding="utf-8"))["high_risk_pr_merge"]["granted"] is True
    assert _git(repo, "log", "-1", "--pretty=%s") == "chore(capabilities): request revoke high_risk_pr_merge"

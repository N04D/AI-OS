from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path

from orchestrator.git import create_governed_commit


@dataclass
class _Result:
    changed_files: list[str]


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    (repo / "a.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init")


def test_create_governed_commit_denied_when_budget_exceeded(tmp_path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)

    (repo / "a.txt").write_text("changed\n", encoding="utf-8")

    budgets = repo / "state" / "budgets.json"
    budgets.parent.mkdir(parents=True, exist_ok=True)
    budgets.write_text(
        json.dumps(
            {
                "version": "v0.1",
                "timezone": "UTC",
                "budgets": {
                    "scheduler_guarded_skill_run": {
                        "window": "daily",
                        "limit": 20,
                        "used": 0,
                        "window_start_utc": None,
                    },
                    "low_risk_pr_merge": {
                        "window": "daily",
                        "limit": 0,
                        "used": 0,
                        "window_start_utc": "2026-02-25T00:00:00Z",
                    },
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)
    result = create_governed_commit(
        _Result(changed_files=["a.txt"]),
        {"allowed_files": ["a.txt"], "task_id": "1"},
        now_utc=datetime(2026, 2, 25, 12, 0, 0, tzinfo=UTC),
        budget_state_path=budgets,
    )

    assert result["commit_created"] is False
    assert result["reason_code"] == "DENY_BUDGET_EXCEEDED"
    assert result["budget_key"] == "low_risk_pr_merge"
    assert result["limit"] == 0
    assert result["used"] == 0
    assert result["window_start_utc"] == "2026-02-25T00:00:00Z"

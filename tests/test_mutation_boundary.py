from __future__ import annotations

import subprocess
from dataclasses import dataclass
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
    (repo / "a.txt").write_text("seed-a\n", encoding="utf-8")
    (repo / "b.txt").write_text("seed-b\n", encoding="utf-8")
    _git(repo, "add", "a.txt", "b.txt")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init")


def test_create_governed_commit_denied_when_changed_files_exceed_allowlist(tmp_path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)

    (repo / "a.txt").write_text("changed-a\n", encoding="utf-8")
    (repo / "b.txt").write_text("changed-b\n", encoding="utf-8")
    before_head = _git(repo, "rev-parse", "HEAD")

    monkeypatch.chdir(repo)
    result = create_governed_commit(
        _Result(changed_files=["a.txt", "b.txt"]),
        {"allowed_files": ["a.txt"], "task_id": "1"},
    )

    after_head = _git(repo, "rev-parse", "HEAD")

    assert result["commit_created"] is False
    assert result["files_committed"] == []
    assert before_head == after_head

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from autonomy_orchestrator.night_mode import NightModeRunner


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.name", "Night Test")
    _git(repo, "config", "user.email", "night-test@example.com")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


def _phase_k_state() -> dict:
    return {
        "agents": {
            "night-mode": {
                "meta": {
                    "trust_level": "MEDIUM",
                    "forced_escalations": 0,
                    "consecutive_clean_epochs": 0,
                    "escalation_token": False,
                },
                "epochs": {},
            }
        },
        "epoch_order": ["2026-02-26"],
        "ledger_chain_status": {"last_verified_epoch": None, "last_hash": ""},
    }


def _phase_j_budget(limit: int) -> dict:
    return {
        "version": "v0.1",
        "timezone": "UTC",
        "budgets": {
            "scheduler_guarded_skill_run": {
                "window": "daily",
                "limit": limit,
                "used": 0,
                "window_start_utc": None,
            },
            "low_risk_pr_merge": {
                "window": "daily",
                "limit": 20,
                "used": 0,
                "window_start_utc": None,
            },
        },
    }


def _make_local_runner(repo: Path) -> NightModeRunner:
    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    enabled_caps = repo / "state" / "capabilities" / "enabled.json"

    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})
    _write_json(enabled_caps, {"enabled": ["filesystem_write"]})

    return NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
    )


def test_local_hello_world_issue_creates_file_and_halts(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issue_path = repo / "state" / "issues" / "open" / "001.json"
    _write_json(
        issue_path,
        {
            "issue_id": "001",
            "labels": ["night-build"],
            "required_capability": "filesystem_write",
            "body": "CREATE_FILE helloworld.txt\nWRITE_FILE helloworld.txt hello world\nCOMMIT local hello\n",
        },
    )
    runner = _make_local_runner(repo)
    result = runner.run()

    assert result["status"] == "halted"
    assert result["summary"]["tasks_executed"] == 1
    assert (repo / "helloworld.txt").read_text(encoding="utf-8") == "hello world\n"
    assert not issue_path.exists()
    messages = _git(repo, "log", "--format=%s").splitlines()
    assert any(msg.startswith("night:001:") for msg in messages)


def test_local_email_issue_missing_capability_emits_request_and_denies(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issue_path = repo / "state" / "issues" / "open" / "010.json"
    _write_json(
        issue_path,
        {
            "issue_id": "010",
            "labels": ["night-build"],
            "required_capability": "email_send",
            "body": "CREATE_FILE email.txt\nWRITE_FILE email.txt mail\nCOMMIT local email\n",
        },
    )
    runner = _make_local_runner(repo)
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_CAPABILITY_MISSING" in result["summary"]["violations"]
    assert issue_path.exists()
    requests = sorted((repo / "state" / "capability_requests").glob("*.json"))
    assert len(requests) == 1
    payload = json.loads(requests[0].read_text(encoding="utf-8"))
    assert payload["type"] == "capability_request"
    assert payload["capability"] == "email_send"
    assert payload["status"] == "requested"


def test_local_queue_recheck_processes_in_order_and_halts_when_empty(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_json(
        repo / "state" / "issues" / "open" / "200.json",
        {
            "issue_id": "200",
            "labels": ["night-build"],
            "required_capability": "filesystem_write",
            "body": "CREATE_FILE b.txt\nWRITE_FILE b.txt b\nCOMMIT b\n",
        },
    )
    _write_json(
        repo / "state" / "issues" / "open" / "100.json",
        {
            "issue_id": "100",
            "labels": ["night-build"],
            "required_capability": "filesystem_write",
            "body": "CREATE_FILE a.txt\nWRITE_FILE a.txt a\nCOMMIT a\n",
        },
    )
    runner = _make_local_runner(repo)
    result = runner.run()

    assert result["status"] == "halted"
    assert result["summary"]["tasks_executed"] == 2
    assert list((repo / "state" / "issues" / "open").glob("*.json")) == []
    messages = _git(repo, "log", "--format=%s").splitlines()
    night_commits = [msg for msg in messages if msg.startswith("night:")]
    assert night_commits[0].startswith("night:200:")
    assert night_commits[1].startswith("night:100:")

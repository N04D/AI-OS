from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import argparse
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from pathlib import Path

from autonomy_orchestrator.night_mode import NightModeRunner
from supervisor.cli import _cmd_night_run
from supervisor.cli import build_parser


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


def _approval_token(scope: list[str], *, exp_offset_s: int = 3600, jti: str = "night-capability-jti") -> str:
    exp = int((datetime.now(UTC) + timedelta(seconds=exp_offset_s)).timestamp())
    return json.dumps({"v": 1, "scope": scope, "exp": exp, "jti": jti}, sort_keys=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.name", "Night Test")
    _git(repo, "config", "user.email", "night-test@example.com")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


class _MockHTTPResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def __enter__(self) -> "_MockHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


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
        "epoch_order": ["2026-02-25", "2026-02-26", "2026-02-27"],
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


def _make_runner(repo: Path, issues: list[dict], *, epoch: str = "2026-02-25") -> NightModeRunner:
    policy_path = Path("/home/infra/AI-OS/governance_policy.yaml")
    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"

    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    return NightModeRunner(
        repo_root=repo,
        epoch_id=epoch,
        policy_path=policy_path,
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        issue_fetcher=lambda: issues,
        plugin_dispatcher=lambda plugin_id, summary: None,
    )


def test_single_issue_single_commit(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [
        {
            "number": 1,
            "body": "CREATE_FILE docs/night.txt\nWRITE_FILE docs/night.txt hello\nCOMMIT write nightly doc\n",
        }
    ]
    runner = _make_runner(repo, issues)

    result = runner.run()
    assert result["status"] == "ok"
    assert result["summary"]["tasks_executed"] == 1

    messages = _git(repo, "log", "--format=%s").splitlines()
    assert any(msg.startswith("night:1:") for msg in messages)


def test_create_write_commit_uses_single_capability_invocation(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [
        {
            "number": 10,
            "body": "CREATE_FILE docs/k.txt\nWRITE_FILE docs/k.txt payload\nCOMMIT k\n",
        }
    ]
    runner = _make_runner(repo, issues)

    calls: list[str] = []

    def _check_capability(capability: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(capability)
        return {"allow": True, "reason_code": None}

    monkeypatch.setattr("autonomy_orchestrator.night_mode.check_capability", _check_capability)
    result = runner.run()

    assert result["status"] == "ok"
    assert result["summary"]["tasks_executed"] == 1
    assert result["summary"]["violations"] == []
    assert calls == ["scheduler_guarded_skill_run"]

    messages = _git(repo, "log", "--format=%s").splitlines()
    assert any(msg.startswith("night:10:") for msg in messages)


def test_multiple_tasks_execute_sequentially(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [
        {
            "number": 2,
            "body": (
                "CREATE_FILE a.txt\n"
                "WRITE_FILE a.txt one\n"
                "COMMIT first\n"
                "CREATE_FILE b.txt\n"
                "WRITE_FILE b.txt two\n"
                "COMMIT second\n"
            ),
        }
    ]
    runner = _make_runner(repo, issues)

    result = runner.run()
    assert result["summary"]["tasks_executed"] == 2
    assert (repo / "a.txt").exists()
    assert (repo / "b.txt").exists()


def test_budget_exhaustion_stops_execution(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [
        {
            "number": 3,
            "body": (
                "CREATE_FILE x.txt\nWRITE_FILE x.txt x\nCOMMIT one\n"
                "CREATE_FILE y.txt\nWRITE_FILE y.txt y\nCOMMIT two\n"
            ),
        }
    ]
    runner = _make_runner(repo, issues)
    _write_json(repo / "state" / "budgets.json", _phase_j_budget(limit=1))

    result = runner.run()
    assert result["status"] == "stopped"
    assert result["summary"]["tasks_executed"] == 1
    assert result["summary"]["tasks_failed"] == 1
    assert "DENY_BUDGET_EXCEEDED" in result["summary"]["violations"]


def test_ledger_invalid_aborts_before_execution(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [{"number": 4, "body": "CREATE_FILE z.txt\nWRITE_FILE z.txt z\nCOMMIT z\n"}]
    runner = _make_runner(repo, issues)

    bad_ledger = repo / "audit" / "budget_ledger" / "2026-02-25.jsonl"
    bad_ledger.parent.mkdir(parents=True, exist_ok=True)
    bad_ledger.write_text('{"event_id":"bad","hash_prev":"x","hash":"y"}\n', encoding="utf-8")

    result = runner.run()
    assert result["status"] == "stopped"
    assert result["summary"]["tasks_executed"] == 0
    assert "DENY_LEDGER_CHAIN_INVALID" in result["summary"]["violations"]


def test_idempotent_rerun_produces_no_new_commits(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [{"number": 5, "body": "CREATE_FILE i.txt\nWRITE_FILE i.txt i\nCOMMIT i\n"}]
    runner = _make_runner(repo, issues)

    first = runner.run()
    first_count = int(_git(repo, "rev-list", "--count", "HEAD"))

    second = runner.run()
    second_count = int(_git(repo, "rev-list", "--count", "HEAD"))

    assert first["summary"]["tasks_executed"] == 1
    assert second["summary"]["tasks_executed"] == 0
    assert second["summary"]["tasks_skipped"] == 1
    assert second_count == first_count


def test_summary_generated_deterministically(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [
        {"number": 6, "body": "CREATE_FILE s1.txt\nWRITE_FILE s1.txt a\nCOMMIT a\n"},
        {"number": 7, "body": "CREATE_FILE s2.txt\nWRITE_FILE s2.txt b\nCOMMIT b\n"},
    ]
    runner = _make_runner(repo, issues)

    result = runner.run()
    summary = result["summary"]
    summary_path = Path(result["summary_path"])

    assert summary_path.exists()
    disk_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert disk_summary == summary
    assert summary["tasks_executed"] == 2
    assert summary["tasks_failed"] == 0
    assert summary["budget_used"] == 2
    assert summary["violations"] == []


def test_missing_budget_engine_state_is_initialized(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [{"number": 61, "body": "CREATE_FILE init.txt\nWRITE_FILE init.txt ok\nCOMMIT init\n"}]

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"

    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})
    if phase_k_state_path.exists():
        phase_k_state_path.unlink()

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        issue_fetcher=lambda: issues,
        plugin_dispatcher=lambda plugin_id, summary: None,
    )

    result = runner.run()
    assert result["status"] == "ok"
    assert result["summary"]["tasks_executed"] == 1
    assert phase_k_state_path.exists()


def test_external_budget_engine_state_uses_external_ledger_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_repo(repo)

    runtime_root = tmp_path / "runtime"
    phase_k_state_path = runtime_root / "state" / "night_mode_state.json"
    phase_j_budget_path = runtime_root / "state" / "budgets.json"
    capability_ledger = runtime_root / "state" / "supervisor_capabilities.json"

    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path,
        capability_ledger_path=capability_ledger,
        issue_fetcher=lambda: [],
        plugin_dispatcher=lambda plugin_id, summary: None,
    )

    assert runner.engine.ledger_root == runtime_root / "audit" / "budget_ledger"


def test_gitea_api_error_is_fail_closed(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _git(repo, "remote", "add", "origin", "git@github.com:org/repo.git")

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"

    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    monkeypatch.chdir(repo)

    def _raise_url_error(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _raise_url_error)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )

    result = runner.run()
    assert result["status"] == "stopped"
    assert result["summary"]["tasks_executed"] == 0
    assert result["summary"]["tasks_failed"] == 1
    assert "DENY_STATE_INVALID" in result["summary"]["violations"]


def test_gitea_issue_lifecycle_success_flow(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"

    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        1: {
            "number": 1,
            "body": "CREATE_FILE docs/g1.txt\nWRITE_FILE docs/g1.txt hello\nCOMMIT g1\n",
            "labels": [{"name": "night-build"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        },
        2: {
            "number": 2,
            "body": "CREATE_FILE docs/g2.txt\nWRITE_FILE docs/g2.txt ignored\nCOMMIT g2\n",
            "labels": [{"name": "night-build"}],
            "assignee": {"username": "other-agent"},
            "state": "open",
        },
    }
    comments: list[tuple[int, str]] = []
    calls: list[tuple[str, str]] = []

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(request, str):
            method = "GET"
            url = request
            body_bytes = b""
        else:
            method = str(getattr(request, "method", "GET"))
            url = str(getattr(request, "full_url"))
            body_bytes = request.data or b""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        calls.append((method, path))

        if method == "GET" and path.endswith("/issues"):
            if query.get("state", [""])[0] != "open":
                raise AssertionError("state=open expected")
            payload = [issue_db[1], issue_db[2]]
            return _MockHTTPResponse(payload)

        if method == "PATCH" and path.endswith("/issues/1"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[1]["labels"] = [{"name": str(label)} for label in labels]
            if payload.get("state") == "closed":
                issue_db[1]["state"] = "closed"
            return _MockHTTPResponse(issue_db[1])

        if method == "POST" and path.endswith("/issues/1/comments"):
            payload = json.loads(body_bytes.decode("utf-8"))
            comments.append((1, str(payload.get("body", ""))))
            return _MockHTTPResponse({"id": len(comments)})

        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )

    result = runner.run()
    assert result["status"] == "halted"
    assert result["summary"]["tasks_executed"] == 1
    assert issue_db[1]["state"] == "closed"
    assert any("Night Mode started at 2026-02-26T00:00:00Z" in message for _, message in comments)
    assert any("Night Mode completed; commits=" in message for _, message in comments)
    final_labels = {item["name"] for item in issue_db[1]["labels"] if isinstance(item, dict)}
    assert "night-build" not in final_labels
    assert "status:completed" in final_labels
    assert all(path != "/api/v1/repos/org/repo/issues/2/comments" for _, path in calls)


def test_gitea_issue_queue_recheck_is_deterministic_and_halts_when_empty(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"

    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        5: {
            "number": 5,
            "body": "CREATE_FILE docs/g5.txt\nWRITE_FILE docs/g5.txt hello\nCOMMIT g5\n",
            "labels": [{"name": "night-build"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        },
        4: {
            "number": 4,
            "body": "CREATE_FILE docs/g4.txt\nWRITE_FILE docs/g4.txt hello\nCOMMIT g4\n",
            "labels": [{"name": "night-build"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        },
    }

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if method == "GET" and path.endswith("/issues"):
            assert query.get("state", [""])[0] == "open"
            payload = [item for item in issue_db.values() if item.get("state") == "open"]
            return _MockHTTPResponse(payload)
        if method == "PATCH" and path.endswith("/issues/4"):
            payload = json.loads(body_bytes.decode("utf-8"))
            if payload.get("state") == "closed":
                issue_db[4]["state"] = "closed"
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[4]["labels"] = [{"name": str(label)} for label in labels]
            return _MockHTTPResponse(issue_db[4])
        if method == "PATCH" and path.endswith("/issues/5"):
            payload = json.loads(body_bytes.decode("utf-8"))
            if payload.get("state") == "closed":
                issue_db[5]["state"] = "closed"
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[5]["labels"] = [{"name": str(label)} for label in labels]
            return _MockHTTPResponse(issue_db[5])
        if method == "POST" and (path.endswith("/issues/4/comments") or path.endswith("/issues/5/comments")):
            return _MockHTTPResponse({"id": 1})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )
    result = runner.run()
    assert result["status"] == "halted"
    assert result["summary"]["tasks_executed"] == 2
    assert issue_db[4]["state"] == "closed"
    assert issue_db[5]["state"] == "closed"
    assert (repo / "logs" / "control" / "night_issue_audit" / "2026-02-26" / "4__detected.json").exists()
    assert (repo / "logs" / "control" / "night_issue_audit" / "2026-02-26" / "4__materialized.json").exists()
    assert (repo / "logs" / "control" / "night_issue_audit" / "2026-02-26" / "4__resolved.json").exists()
    assert (repo / "logs" / "control" / "night_issue_audit" / "2026-02-26" / "5__detected.json").exists()


def test_gitea_issue_lifecycle_failure_marks_blocked(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"

    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        3: {
            "number": 3,
            "body": "CREATE_FILE docs/f3.txt\nWRITE_FILE docs/f3.txt fail\nCOMMIT f3\n",
            "labels": [{"name": "night-build"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        }
    }
    comments: list[str] = []

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path

        if method == "GET" and path.endswith("/issues"):
            return _MockHTTPResponse([issue_db[3]])
        if method == "PATCH" and path.endswith("/issues/3"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[3]["labels"] = [{"name": str(label)} for label in labels]
            if payload.get("state") == "closed":
                issue_db[3]["state"] = "closed"
            return _MockHTTPResponse(issue_db[3])
        if method == "POST" and path.endswith("/issues/3/comments"):
            payload = json.loads(body_bytes.decode("utf-8"))
            comments.append(str(payload.get("body", "")))
            return _MockHTTPResponse({"id": len(comments)})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    monkeypatch.setattr(
        "autonomy_orchestrator.night_mode.check_capability",
        lambda *args, **kwargs: {"allow": False, "reason_code": "DENY_CAPABILITY_MISSING"},
    )

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )

    result = runner.run()
    assert result["status"] == "stopped"
    assert "DENY_CAPABILITY_MISSING" in result["summary"]["violations"]
    assert issue_db[3]["state"] == "open"
    labels = {item["name"] for item in issue_db[3]["labels"] if isinstance(item, dict)}
    assert "status:blocked" in labels
    assert any("Night Mode blocked; reason_code=DENY_CAPABILITY_MISSING" in message for message in comments)


def test_missing_capability_writes_capability_request_artifact(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", _approval_token(["capability_execution"], jti="cap-req-jti"))

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        13: {
            "number": 13,
            "body": "CREATE_FILE docs/s13.txt\nWRITE_FILE docs/s13.txt x\nCOMMIT s13\n",
            "labels": [{"name": "night-build"}, {"name": "self-improvement"}, {"name": "risk:low"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        }
    }

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        path = urllib.parse.urlparse(url).path
        if method == "GET" and path.endswith("/issues"):
            return _MockHTTPResponse([issue_db[13]])
        if method == "PATCH" and path.endswith("/issues/13"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[13]["labels"] = [{"name": str(label)} for label in labels]
            return _MockHTTPResponse(issue_db[13])
        if method == "POST" and path.endswith("/issues/13/comments"):
            return _MockHTTPResponse({"id": 1})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    monkeypatch.setattr(
        "autonomy_orchestrator.night_mode.check_capability",
        lambda *args, **kwargs: {"allow": False, "reason_code": "DENY_CAPABILITY_MISSING"},
    )

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )
    result = runner.run()
    assert result["status"] == "stopped"
    assert "DENY_CAPABILITY_MISSING" in result["summary"]["violations"]
    ledger_after = json.loads((repo / "state" / "supervisor_capabilities.json").read_text(encoding="utf-8"))
    assert ledger_after["scheduler_guarded_skill_run"] is True
    requests_root = repo / "requests" / "capabilities" / "night_mode"
    entries = sorted(requests_root.glob("*.json"))
    assert len(entries) == 1
    payload = json.loads(entries[0].read_text(encoding="utf-8"))
    assert payload["type"] == "capability_request"
    assert payload["required_capability"] == "scheduler_guarded_skill_run"
    assert payload["reason_code"] == "DENY_CAPABILITY_MISSING"
    assert payload["status"] == "requested"


def test_high_risk_self_improvement_capability_execution_denied_without_token(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.delenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", raising=False)

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        15: {
            "number": 15,
            "body": "CREATE_FILE docs/s15.txt\nWRITE_FILE docs/s15.txt x\nCOMMIT s15\n",
            "labels": [{"name": "night-build"}, {"name": "self-improvement"}, {"name": "risk:high"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        }
    }

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        path = urllib.parse.urlparse(url).path
        if method == "GET" and path.endswith("/issues"):
            return _MockHTTPResponse([issue_db[15]])
        if method == "PATCH" and path.endswith("/issues/15"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[15]["labels"] = [{"name": str(label)} for label in labels]
            return _MockHTTPResponse(issue_db[15])
        if method == "POST" and path.endswith("/issues/15/comments"):
            return _MockHTTPResponse({"id": 1})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )
    result = runner.run()
    assert result["status"] == "stopped"
    assert "DENY_TOKEN_MISSING" in result["summary"]["violations"]


def test_self_improvement_missing_risk_label_is_denied(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", _approval_token(["capability_execution"], jti="risk-jti"))

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        17: {
            "number": 17,
            "body": "CREATE_FILE docs/s17.txt\nWRITE_FILE docs/s17.txt x\nCOMMIT s17\n",
            "labels": [{"name": "night-build"}, {"name": "self-improvement"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        }
    }

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        path = urllib.parse.urlparse(url).path
        if method == "GET" and path.endswith("/issues"):
            return _MockHTTPResponse([issue_db[17]])
        if method == "PATCH" and path.endswith("/issues/17"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[17]["labels"] = [{"name": str(label)} for label in labels]
            return _MockHTTPResponse(issue_db[17])
        if method == "POST" and path.endswith("/issues/17/comments"):
            return _MockHTTPResponse({"id": 1})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )
    result = runner.run()
    assert result["status"] == "stopped"
    assert "DENY_STATE_INVALID" in result["summary"]["violations"]


def test_self_improvement_med_runtime_generates_determinism_evidence(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", _approval_token(["capability_execution"], jti="det-jti-01"))

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})

    issue_db: dict[int, dict[str, object]] = {
        18: {
            "number": 18,
            "body": "CREATE_FILE supervisor/s18.txt\nWRITE_FILE supervisor/s18.txt x\nCOMMIT s18\n",
            "labels": [{"name": "night-build"}, {"name": "self-improvement"}, {"name": "risk:med"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        }
    }

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        path = urllib.parse.urlparse(url).path
        if method == "GET" and path.endswith("/issues"):
            return _MockHTTPResponse([issue_db[18]])
        if method == "PATCH" and path.endswith("/issues/18"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[18]["labels"] = [{"name": str(label)} for label in labels]
            if payload.get("state") == "closed":
                issue_db[18]["state"] = "closed"
            return _MockHTTPResponse(issue_db[18])
        if method == "POST" and path.endswith("/issues/18/comments"):
            return _MockHTTPResponse({"id": 1})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )
    result = runner.run()
    assert result["status"] == "halted"
    evidence = sorted((repo / "logs" / "control" / "night_runs" / "2026-02-26" / "determinism").glob("18__*.json"))
    assert len(evidence) == 1
    payload = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert payload["risk_tier"] == "MED"
    assert payload["rerun_consistent"] is True


def test_self_improvement_runtime_enforces_improvement_budget_limit(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", _approval_token(["capability_execution"], jti="budget-jti"))

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    _write_json(phase_k_state_path, _phase_k_state())
    _write_json(phase_j_budget_path, _phase_j_budget(limit=20))
    _write_json(capability_ledger, {"scheduler_guarded_skill_run": True})
    _write_json(
        repo / "autonomy" / "budget.json",
        {
            "version": "autonomy-budget.v0.1",
            "window_utc_day": "2026-02-26",
            "counts": {
                "promotion": 0,
                "intake": 0,
                "materialize": 0,
                "exec_attempt": 0,
                "commit": 0,
                "improvement": 8,
            },
            "last_action_epoch_s": {
                "promotion": 0,
                "intake": 0,
                "materialize": 0,
                "exec_attempt": 0,
                "commit": 0,
                "improvement": 0,
            },
            "last_consume_keys": {
                "promotion": "",
                "intake": "",
                "materialize": "",
                "exec_attempt": "",
                "commit": "",
                "improvement": "",
            },
            "daily_limits": {
                "promotion": 10,
                "intake": 20,
                "materialize": 20,
                "exec_attempt": 30,
                "commit": 5,
                "improvement": 8,
            },
            "cooldowns_seconds": {
                "promotion": 60,
                "intake": 15,
                "materialize": 15,
                "exec_attempt": 5,
                "commit": 0,
                "improvement": 0,
            },
        },
    )

    issue_db: dict[int, dict[str, object]] = {
        16: {
            "number": 16,
            "body": "CREATE_FILE supervisor/s16.txt\nWRITE_FILE supervisor/s16.txt x\nCOMMIT s16\n",
            "labels": [{"name": "night-build"}, {"name": "self-improvement"}, {"name": "risk:low"}],
            "assignee": {"username": "night-mode"},
            "state": "open",
        }
    }

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        method = str(getattr(request, "method", "GET"))
        url = str(getattr(request, "full_url"))
        body_bytes = request.data or b""
        path = urllib.parse.urlparse(url).path
        if method == "GET" and path.endswith("/issues"):
            return _MockHTTPResponse([issue_db[16]])
        if method == "PATCH" and path.endswith("/issues/16"):
            payload = json.loads(body_bytes.decode("utf-8"))
            labels = payload.get("labels", [])
            if isinstance(labels, list):
                issue_db[16]["labels"] = [{"name": str(label)} for label in labels]
            return _MockHTTPResponse(issue_db[16])
        if method == "POST" and path.endswith("/issues/16/comments"):
            return _MockHTTPResponse({"id": 1})
        raise AssertionError(f"unexpected api call: {method} {path}")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    runner = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-26",
        policy_path=Path("/home/infra/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        agent_id="night-mode",
        gitea_base_url="http://127.0.0.1:3000",
        gitea_token="token",
        gitea_repo="org/repo",
    )
    result = runner.run()
    assert result["status"] == "stopped"
    assert "DENY_BUDGET_EXCEEDED" in result["summary"]["violations"]


def test_summary_dir_missing_is_created_and_written(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [{"number": 8, "body": "CREATE_FILE m.txt\nWRITE_FILE m.txt m\nCOMMIT m\n"}]
    runner = _make_runner(repo, issues)

    summary_root = repo / "state" / "runtime" / "night_runs"
    if summary_root.exists():
        raise AssertionError("summary dir should not exist before run")

    result = runner.run()
    assert result["status"] == "ok"
    assert summary_root.exists() and summary_root.is_dir()
    summary_path = Path(result["summary_path"])
    assert summary_path.exists()


def test_summary_dir_read_only_fails_with_controlled_error(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)

    issues = [{"number": 9, "body": "CREATE_FILE r.txt\nWRITE_FILE r.txt r\nCOMMIT r\n"}]
    runner = _make_runner(repo, issues)

    summary_root = repo / "state" / "runtime" / "night_runs"
    summary_root.mkdir(parents=True, exist_ok=True)
    summary_root.chmod(0o555)

    try:
        with pytest.raises(RuntimeError, match="night_run_output_not_writable"):
            runner.run()
    finally:
        summary_root.chmod(0o755)


def test_cli_night_run_without_flags_uses_defaults(monkeypatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["night-run"])
    assert args.epoch == ""
    assert args.capability_ledger_path == "state/supervisor_capabilities.json"
    assert args.budget_engine_state_path == "state/budgets.json"
    assert args.budget_state_path == "state/budgets.json"
    assert args.ledger_root == "audit/budget_ledger"
    assert args.summary_dir == "logs/control/night_runs"
    assert args.specs_dir == "state/night_specs"
    assert args.remote_config_path == "config/remote_sources.yaml"


def test_cli_night_run_missing_env_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(
        source="gitea",
        epoch="",
        policy_path="governance_policy.yaml",
        budget_engine_state_path="state/budgets.json",
        budget_state_path="state/budgets.json",
        capability_ledger_path="state/supervisor_capabilities.json",
        capability_denylist_path="state/supervisor_capability_denies.json",
        ledger_root="audit/budget_ledger",
        specs_dir="state/night_specs",
        summary_dir="logs/control/night_runs",
        remote_config_path="config/remote_sources.yaml",
    )
    for key in ("GITEA_BASE_URL", "GITEA_TOKEN", "GITEA_REPO", "NIGHT_AGENT_ID"):
        monkeypatch.delenv(key, raising=False)
    exit_code, payload, kind = _cmd_night_run(args)
    assert kind == "night_run"
    assert exit_code == 2
    assert payload["status"] == "rejected"
    assert payload["reason_code"] == "DENY_STATE_INVALID"
    assert "missing_env:" in payload["reason"]


def test_cli_night_run_success_uses_default_paths(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    monkeypatch.chdir(repo)
    captured: dict[str, object] = {}

    class _StubRunner:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)

        def run(self) -> dict[str, object]:
            return {
                "status": "ok",
                "summary": {
                    "tasks_executed": 0,
                    "tasks_skipped": 0,
                    "tasks_failed": 0,
                    "budget_used": 0,
                    "violations": [],
                },
                "summary_path": "logs/control/night_runs/2026-02-26.json",
            }

    monkeypatch.setattr("supervisor.cli.NightModeRunner", _StubRunner)
    monkeypatch.setenv("GITEA_BASE_URL", "http://127.0.0.1:3000")
    monkeypatch.setenv("GITEA_TOKEN", "token")
    monkeypatch.setenv("GITEA_REPO", "org/repo")
    monkeypatch.setenv("NIGHT_AGENT_ID", "night-mode")

    args = argparse.Namespace(
        source="gitea",
        epoch="",
        policy_path="governance_policy.yaml",
        budget_engine_state_path="state/budgets.json",
        budget_state_path="state/budgets.json",
        capability_ledger_path="state/supervisor_capabilities.json",
        capability_denylist_path="state/supervisor_capability_denies.json",
        ledger_root="audit/budget_ledger",
        specs_dir="state/night_specs",
        summary_dir="logs/control/night_runs",
        remote_config_path="config/remote_sources.yaml",
    )
    exit_code, payload, kind = _cmd_night_run(args)

    assert kind == "night_run"
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert captured["repo_root"] == repo
    assert captured["capability_ledger_path"] == Path("state/supervisor_capabilities.json")
    assert captured["budget_engine_state_path"] == Path("state/budgets.json")
    assert captured["budget_state_path"] == Path("state/budgets.json")
    assert captured["ledger_root"] == Path("audit/budget_ledger")
    assert captured["summary_dir"] == Path("logs/control/night_runs")
    assert captured["specs_dir"] == Path("state/night_specs")
    assert captured["agent_id"] == "night-mode"
    assert captured["source_mode"] == "gitea"
    assert captured["remote_config_path"] == Path("config/remote_sources.yaml")
    assert captured["gitea_base_url"] == "http://127.0.0.1:3000"
    assert captured["gitea_token"] == "token"
    assert captured["gitea_repo"] == "org/repo"
    assert isinstance(captured["epoch_id"], str) and len(str(captured["epoch_id"])) == 10


def test_cli_night_run_local_source_does_not_require_gitea_env(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    monkeypatch.chdir(repo)
    captured: dict[str, object] = {}

    class _StubRunner:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)

        def run(self) -> dict[str, object]:
            return {
                "status": "ok",
                "summary": {
                    "tasks_executed": 0,
                    "tasks_skipped": 0,
                    "tasks_failed": 0,
                    "budget_used": 0,
                    "violations": [],
                },
                "summary_path": "logs/control/night_runs/2026-02-26.json",
            }

    monkeypatch.setattr("supervisor.cli.NightModeRunner", _StubRunner)
    for key in ("GITEA_BASE_URL", "GITEA_TOKEN", "GITEA_REPO", "NIGHT_AGENT_ID"):
        monkeypatch.delenv(key, raising=False)

    args = argparse.Namespace(
        source="local",
        epoch="2026-02-26",
        policy_path="/home/infra/AI-OS/governance_policy.yaml",
        budget_engine_state_path="state/budgets.json",
        budget_state_path="state/budgets.json",
        capability_ledger_path="state/supervisor_capabilities.json",
        capability_denylist_path="state/supervisor_capability_denies.json",
        ledger_root="audit/budget_ledger",
        specs_dir="state/night_specs",
        summary_dir="logs/control/night_runs",
        remote_config_path="config/remote_sources.yaml",
    )
    exit_code, payload, kind = _cmd_night_run(args)

    assert kind == "night_run"
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert captured["source_mode"] == "local"
    assert captured["remote_config_path"] == Path("config/remote_sources.yaml")
    assert captured["gitea_base_url"] == ""
    assert captured["gitea_token"] == ""
    assert captured["gitea_repo"] == ""


def test_cli_night_run_remote_source_does_not_require_gitea_env(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    monkeypatch.chdir(repo)
    captured: dict[str, object] = {}

    class _StubRunner:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)

        def run(self) -> dict[str, object]:
            return {
                "status": "ok",
                "summary": {
                    "tasks_executed": 0,
                    "tasks_skipped": 0,
                    "tasks_failed": 0,
                    "budget_used": 0,
                    "violations": [],
                },
                "summary_path": "logs/control/night_runs/2026-02-26.json",
            }

    monkeypatch.setattr("supervisor.cli.NightModeRunner", _StubRunner)
    for key in ("GITEA_BASE_URL", "GITEA_TOKEN", "GITEA_REPO", "NIGHT_AGENT_ID"):
        monkeypatch.delenv(key, raising=False)

    args = argparse.Namespace(
        source="remote",
        epoch="2026-02-26",
        policy_path="/home/infra/AI-OS/governance_policy.yaml",
        budget_engine_state_path="state/budgets.json",
        budget_state_path="state/budgets.json",
        capability_ledger_path="state/supervisor_capabilities.json",
        capability_denylist_path="state/supervisor_capability_denies.json",
        ledger_root="audit/budget_ledger",
        specs_dir="state/night_specs",
        summary_dir="logs/control/night_runs",
        remote_config_path="config/remote_sources.yaml",
    )
    exit_code, payload, kind = _cmd_night_run(args)

    assert kind == "night_run"
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert captured["source_mode"] == "remote"
    assert captured["gitea_base_url"] == ""
    assert captured["gitea_token"] == ""
    assert captured["gitea_repo"] == ""


def test_three_consecutive_night_runs_succeed(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issues = [{"number": 70, "body": "CREATE_FILE docs/r70.txt\nWRITE_FILE docs/r70.txt ok\nCOMMIT r70\n"}]
    runner = _make_runner(repo, issues, epoch="2026-02-26")

    first = runner.run()
    second = runner.run()
    third = runner.run()

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert third["status"] == "ok"
    assert first["summary"]["tasks_executed"] == 1
    assert second["summary"]["tasks_skipped"] == 1
    assert third["summary"]["tasks_skipped"] == 1


def _run_single_epoch(repo: Path, issue_number: int) -> tuple[dict, str]:
    _init_repo(repo)
    issues = [
        {
            "number": issue_number,
            "body": f"CREATE_FILE docs/{issue_number}.txt\nWRITE_FILE docs/{issue_number}.txt hello\nCOMMIT n{issue_number}\n",
        }
    ]
    runner = _make_runner(repo, issues, epoch="2026-02-26")
    result = runner.run()
    ledger_path = repo / "audit" / "budget_ledger" / "2026-02-26.jsonl"
    return result["summary"], ledger_path.read_text(encoding="utf-8")


def test_identical_output_for_identical_state(tmp_path: Path) -> None:
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_a.mkdir(parents=True, exist_ok=True)
    repo_b.mkdir(parents=True, exist_ok=True)

    summary_a, ledger_a = _run_single_epoch(repo_a, 80)
    summary_b, ledger_b = _run_single_epoch(repo_b, 80)

    assert summary_a == summary_b
    assert ledger_a == ledger_b


def test_summary_has_only_controlled_time_field(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issues = [{"number": 90, "body": "CREATE_FILE docs/t90.txt\nWRITE_FILE docs/t90.txt x\nCOMMIT t90\n"}]
    runner = _make_runner(repo, issues, epoch="2026-02-26")
    result = runner.run()

    summary = result["summary"]
    assert set(summary.keys()) == {
        "epoch",
        "tasks_executed",
        "tasks_skipped",
        "tasks_failed",
        "budget_used",
        "violations",
        "stopped",
    }
    assert summary["epoch"] == "2026-02-26"


def test_interrupt_flag_halts_at_phase_boundary(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issues = [
        {
            "number": 91,
            "body": "CREATE_FILE docs/phase_boundary.txt\nWRITE_FILE docs/phase_boundary.txt payload\nCOMMIT phase boundary\n",
        }
    ]
    runner = _make_runner(repo, issues, epoch="2026-02-25")
    autonomy_state_path = repo / "state" / "autonomy_state.json"
    _write_json(autonomy_state_path, {"INTERRUPT_FLAG": True})

    result = runner.run()
    assert result["status"] == "halted"
    assert result["summary"]["tasks_executed"] == 0
    assert "DENY_INTERRUPT_REQUESTED" in result["summary"]["violations"]
    artifact = repo / "logs" / "control" / "interrupts" / "2026-02-25" / "interrupt__phase_boundary.json"
    assert artifact.exists()
    assert not (repo / "docs" / "phase_boundary.txt").exists()


def test_interrupt_flag_before_budget_consume_halts_deterministically(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issues = [
        {
            "number": 92,
            "body": "CREATE_FILE docs/pre_budget.txt\nWRITE_FILE docs/pre_budget.txt payload\nCOMMIT pre budget\n",
        }
    ]
    runner = _make_runner(repo, issues, epoch="2026-02-25")
    calls = {"count": 0}

    def _interrupt_sequence() -> bool:
        calls["count"] += 1
        return calls["count"] >= 2

    runner._read_interrupt_flag = _interrupt_sequence  # type: ignore[method-assign]
    result = runner.run()

    assert result["status"] == "halted"
    assert result["summary"]["tasks_executed"] == 0
    assert "DENY_INTERRUPT_REQUESTED" in result["summary"]["violations"]
    artifact = repo / "logs" / "control" / "interrupts" / "2026-02-25" / "interrupt__before_budget_consume.json"
    assert artifact.exists()


def test_night_mode_denies_on_budget_state_tamper(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    issues = [{"number": 93, "body": "CREATE_FILE docs/t93.txt\nWRITE_FILE docs/t93.txt x\nCOMMIT t93\n"}]
    runner = _make_runner(repo, issues, epoch="2026-02-25")

    first = runner.run()
    assert first["status"] == "ok"

    (repo / "state" / "budgets.json").write_text(
        '{"version":"v0.1","timezone":"UTC","budgets":{"tampered":{"bad":1}}}\n',
        encoding="utf-8",
    )
    second = runner.run()
    assert second["status"] == "stopped"
    assert "DENY_STATE_INTEGRITY" in second["summary"]["violations"]

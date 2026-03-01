from __future__ import annotations

import json
import subprocess
import urllib.error
from hashlib import sha256
from pathlib import Path
from typing import Any

from autonomy_orchestrator.night_mode import NightModeRunner


class _MockHTTPResponse:
    def __init__(self, payload: Any, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._headers = headers or {}
        self._body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    @property
    def headers(self):  # type: ignore[no-untyped-def]
        return self

    def get(self, key: str, default: str = "") -> str:
        return self._headers.get(key, default)

    def getcode(self) -> int:
        return self.status

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


class _MockInvalidJSONResponse:
    def __init__(self, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._headers = headers or {}

    def read(self) -> bytes:
        return b"{invalid-json"

    @property
    def headers(self):  # type: ignore[no-untyped-def]
        return self

    def get(self, key: str, default: str = "") -> str:
        return self._headers.get(key, default)

    def getcode(self) -> int:
        return self.status

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _sha256_tree(root: Path) -> str:
    rows: list[str] = []
    if not root.exists():
        return sha256(b"").hexdigest()
    for path in sorted([p for p in root.rglob("*") if p.is_file()], key=lambda p: str(p.relative_to(root))):
        rel = str(path.relative_to(root))
        rows.append(f"{rel}:{sha256(path.read_bytes()).hexdigest()}")
    payload = "\n".join(rows) + ("\n" if rows else "")
    return sha256(payload.encode("utf-8")).hexdigest()


def _normalize_for_compare(payload: Any, *, repo_root: Path) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key in sorted(payload.keys()):
            value = payload[key]
            if key == "epoch":
                out[key] = "<epoch>"
            else:
                out[key] = _normalize_for_compare(value, repo_root=repo_root)
        return out
    if isinstance(payload, list):
        return [_normalize_for_compare(item, repo_root=repo_root) for item in payload]
    if isinstance(payload, str):
        normalized = payload.replace(str(repo_root), "<repo>")
        return normalized
    return payload


def _normalized_json_tree_hash(root: Path, *, repo_root: Path) -> str:
    rows: list[str] = []
    for path in sorted(root.rglob("*.json"), key=lambda p: str(p.relative_to(root))):
        rel = str(path.relative_to(root))
        payload = json.loads(path.read_text(encoding="utf-8"))
        normalized = _normalize_for_compare(payload, repo_root=repo_root)
        rows.append(f"{rel}:{json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=True)}")
    blob = "\n".join(rows) + ("\n" if rows else "")
    return sha256(blob.encode("utf-8")).hexdigest()


def _normalized_json_without_epoch(payload: Any) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key in sorted(payload.keys()):
            if key == "epoch":
                out[key] = "<epoch>"
            else:
                out[key] = _normalized_json_without_epoch(payload[key])
        return out
    if isinstance(payload, list):
        return [_normalized_json_without_epoch(item) for item in payload]
    return payload


def _assert_no_forbidden_time_fields(path: Path) -> None:
    forbidden = {
        "created_at",
        "updated_at",
        "timestamp",
        "generated_at",
        "wall_clock",
        "runtime_now",
    }
    if not path.exists():
        return
    json_paths: list[Path]
    if path.is_file() and path.suffix == ".json":
        json_paths = [path]
    else:
        json_paths = sorted(path.rglob("*.json"), key=lambda p: str(p))
    for json_path in json_paths:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        stack: list[Any] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    assert key not in forbidden, f"forbidden field {key} in {json_path}"
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)


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
        "epoch_order": ["2026-02-27"],
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


def _write_remote_config(repo: Path, *, provider: str = "gitea", enabled: bool = True) -> None:
    base_url = "https://gitea.example.com/api/v1" if provider == "gitea" else "https://api.github.com"
    token_env = "GITEA_TOKEN" if provider == "gitea" else "GITHUB_TOKEN"
    payload = {
        "remote_sources": [
            {
                "id": f"{provider}-main",
                "type": provider,
                "enabled": enabled,
                "base_url": base_url,
                "owner": "N04D",
                "repo": "AI-OS",
                "auth_env": token_env,
                "labels_allowlist": ["aios"],
                "max_issues": 100,
            }
        ]
    }
    repo.joinpath("config").mkdir(parents=True, exist_ok=True)
    import yaml

    repo.joinpath("config", "remote_sources.yaml").write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")


def _make_runner(repo: Path, *, source_mode: str = "remote", epoch: str = "2026-02-27") -> NightModeRunner:
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
        epoch_id=epoch,
        policy_path=Path("/data/srv/aios/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        source_mode=source_mode,
        remote_config_path=Path("config/remote_sources.yaml"),
    )


def test_remote_gitea_issue_executes_deterministically(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        url = str(getattr(request, "full_url"))
        assert "/repos/N04D/AI-OS/issues" in url
        payload = [
            {
                "number": 12,
                "title": "remote low",
                "body": "CREATE_FILE remote_gitea.txt\nWRITE_FILE remote_gitea.txt ok\nCOMMIT rg\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"ETag": "W/etag-1", "X-RateLimit-Remaining": "10"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] in {"halted", "ok"}
    assert result["summary"]["tasks_executed"] == 1
    assert (repo / "remote_gitea.txt").read_text(encoding="utf-8") == "ok\n"
    audit = json.loads((repo / "logs" / "control" / "remote_sync" / "2026-02-27.json").read_text(encoding="utf-8"))
    assert audit["sources"][0]["source"] == "gitea-main"
    assert audit["sources"][0]["issue_count"] == 1
    assert isinstance(audit["sources"][0]["normalized_hash"], str) and len(audit["sources"][0]["normalized_hash"]) == 64


def test_remote_github_issue_executes_deterministically(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="github", enabled=True)
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        url = str(getattr(request, "full_url"))
        assert "api.github.com/repos/N04D/AI-OS/issues" in url
        payload = [
            {
                "number": 15,
                "title": "remote low gh",
                "body": "CREATE_FILE remote_github.txt\nWRITE_FILE remote_github.txt ok\nCOMMIT rgh\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"ETag": "W/etag-gh", "X-RateLimit-Remaining": "10"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["summary"]["tasks_executed"] == 1
    assert (repo / "remote_github.txt").read_text(encoding="utf-8") == "ok\n"


def test_remote_refetch_same_epoch_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    calls = {"count": 0}

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if calls["count"] == 1:
            payload = [
                {
                    "number": 88,
                    "title": "det",
                    "body": "CREATE_FILE det.txt\nWRITE_FILE det.txt d\nCOMMIT det\n",
                    "labels": [{"name": "aios"}, {"name": "LOW"}],
                }
            ]
            return _MockHTTPResponse(payload, status=200, headers={"ETag": "W/etag-det", "X-RateLimit-Remaining": "10"})
        return _MockHTTPResponse([], status=304, headers={"ETag": "W/etag-det", "X-RateLimit-Remaining": "10"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    first = _make_runner(repo, source_mode="remote", epoch="2026-02-27")
    first._fetch_remote_open_issues()  # noqa: SLF001
    artifact = repo / "logs" / "control" / "remote_sync" / "2026-02-27.json"
    hash_a = sha256(artifact.read_bytes()).hexdigest()

    second = _make_runner(repo, source_mode="remote", epoch="2026-02-27")
    second._fetch_remote_open_issues()  # noqa: SLF001
    hash_b = sha256(artifact.read_bytes()).hexdigest()

    assert hash_a == hash_b


def test_remote_high_without_token_denies(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")
    monkeypatch.delenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", raising=False)

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 55,
                "title": "high",
                "body": "CREATE_FILE high.txt\nWRITE_FILE high.txt h\nCOMMIT high\n",
                "labels": [{"name": "aios"}, {"name": "HIGH"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_TOKEN_MISSING" in result["summary"]["violations"]


def test_remote_med_missing_capability_emits_request(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 44,
                "title": "med cap",
                "body": "CREATE_FILE med.txt\nWRITE_FILE med.txt m\nCOMMIT med\n",
                "labels": [{"name": "aios"}, {"name": "MED"}, {"name": "capability:email_send"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_CAPABILITY_MISSING" in result["summary"]["violations"]
    reqs = sorted((repo / "state" / "capability_requests").glob("*.json"))
    assert len(reqs) == 1
    req = json.loads(reqs[0].read_text(encoding="utf-8"))
    assert req["capability"] == "email_send"


def test_remote_disabled_sources_skip_fetch(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=False)

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("remote fetch should not be called when disabled")

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "ok"
    assert result["summary"]["tasks_executed"] == 0


def test_remote_issue_replay_denied_by_execution_ledger(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 77,
                "title": "remote replay",
                "body": "CREATE_FILE replay.txt\nWRITE_FILE replay.txt once\nCOMMIT replay\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/replay"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    first = _make_runner(repo, source_mode="remote", epoch="2026-02-27")
    first_result = first.run()
    assert first_result["summary"]["tasks_executed"] == 1
    assert (repo / "replay.txt").read_text(encoding="utf-8") == "once\n"

    phase_k_state_path = repo / "state" / "night_mode_state.json"
    phase_j_budget_path = repo / "state" / "budgets.json"
    capability_ledger = repo / "state" / "supervisor_capabilities.json"
    second = NightModeRunner(
        repo_root=repo,
        epoch_id="2026-02-28",
        policy_path=Path("/data/srv/aios/AI-OS/governance_policy.yaml"),
        budget_engine_state_path=phase_k_state_path,
        budget_state_path=phase_j_budget_path.relative_to(repo),
        capability_ledger_path=capability_ledger.relative_to(repo),
        plugin_dispatcher=lambda plugin_id, summary: None,
        source_mode="remote",
        remote_config_path=Path("config/remote_sources.yaml"),
    )
    second_result = second.run()
    assert second_result["status"] == "stopped"
    assert "DENY_ALREADY_EXECUTED" in second_result["summary"]["violations"]
    assert second_result["summary"]["tasks_executed"] == 0

    ledger_path = repo / "state" / "issues" / "remote" / "remote_issue_execution_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert "remote:gitea-main:77" in ledger["executed_issue_ids"]

    replay_audit = repo / "logs" / "control" / "night_issue_audit" / "2026-02-28" / "remote:gitea-main:77__replay_denied.json"
    assert replay_audit.exists()
    payload = json.loads(replay_audit.read_text(encoding="utf-8"))
    assert payload["reason_code"] == "DENY_ALREADY_EXECUTED"


def test_remote_risk_tier_detection_is_deterministic_for_low_med_high(tmp_path: Path) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=False)
    runner = _make_runner(repo, source_mode="remote")

    samples = [
        ([{"name": "aios"}, {"name": "LOW"}], "LOW"),
        ([{"name": "aios"}, {"name": "MED"}], "MED"),
        ([{"name": "aios"}, {"name": "HIGH"}], "HIGH"),
    ]
    for labels, expected_tier in samples:
        issue = {
            "number": 101,
            "title": f"{expected_tier} tier",
            "body": "CREATE_FILE tier.txt\nWRITE_FILE tier.txt ok\nCOMMIT tier\n",
            "labels": labels,
        }
        first = runner._normalize_remote_issue("gitea-main", issue.copy())  # noqa: SLF001
        second = runner._normalize_remote_issue("gitea-main", issue.copy())  # noqa: SLF001
        assert first["risk_tier"] == expected_tier
        assert second["risk_tier"] == expected_tier
        assert first == second


def test_source_both_merge_order_is_stable(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    local_open = repo / "state" / "issues" / "open"
    local_open.mkdir(parents=True, exist_ok=True)
    _write_json(
        local_open / "002-local-low.json",
        {
            "id": "002-local-low",
            "title": "local low",
            "labels": ["self-improvement", "LOW"],
            "body": "CREATE_FILE local_order.txt\nWRITE_FILE local_order.txt local\nCOMMIT local-order\n",
        },
    )

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 1,
                "title": "remote low",
                "body": "CREATE_FILE remote_order.txt\nWRITE_FILE remote_order.txt remote\nCOMMIT remote-order\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/both"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="both")
    result = runner.run()
    assert result["summary"]["tasks_executed"] == 2

    subjects = _git(repo, "log", "--format=%s", "-n", "2").splitlines()
    assert len(subjects) == 2
    assert subjects[0].startswith("night:002-local-low:")
    assert subjects[1].startswith("night:remote:gitea-main:1:")


def test_source_both_fetch_order_is_deterministic_across_repeated_runs(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    local_open = repo / "state" / "issues" / "open"
    local_open.mkdir(parents=True, exist_ok=True)
    _write_json(
        local_open / "010-local-low.json",
        {
            "id": "010-local-low",
            "title": "local low",
            "labels": ["self-improvement", "LOW"],
            "body": "CREATE_FILE local_a.txt\nWRITE_FILE local_a.txt a\nCOMMIT local-a\n",
        },
    )

    calls = {"count": 0}

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if calls["count"] == 1:
            payload = [
                {
                    "number": 2,
                    "title": "remote low",
                    "body": "CREATE_FILE remote_a.txt\nWRITE_FILE remote_a.txt r\nCOMMIT remote-a\n",
                    "labels": [{"name": "aios"}, {"name": "LOW"}],
                }
            ]
            return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/det"})
        return _MockHTTPResponse([], status=304, headers={"X-RateLimit-Remaining": "10", "ETag": "W/det"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)

    first = _make_runner(repo, source_mode="both", epoch="2026-02-27")
    first_items = first._fetch_local_and_remote_open_issues()  # noqa: SLF001
    first_order = [str(item.get("number")) for item in first_items]

    second = _make_runner(repo, source_mode="both", epoch="2026-02-27")
    second_items = second._fetch_local_and_remote_open_issues()  # noqa: SLF001
    second_order = [str(item.get("number")) for item in second_items]

    assert first_order == second_order


def test_remote_401_fails_closed_without_partial_intake(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(
            url=str(getattr(request, "full_url")),
            code=401,
            msg="unauthorized",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_STATE_INVALID" in result["summary"]["violations"]
    remote_dir = repo / "state" / "issues" / "remote" / "gitea-main"
    assert not remote_dir.exists() or not any(remote_dir.glob("*.json"))


def test_remote_429_rate_limit_fails_closed(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        return _MockHTTPResponse([], status=429, headers={"X-RateLimit-Remaining": "0"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_STATE_INVALID" in result["summary"]["violations"]
    remote_dir = repo / "state" / "issues" / "remote" / "gitea-main"
    assert not remote_dir.exists() or not any(remote_dir.glob("*.json"))


def test_remote_invalid_json_fails_closed(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        return _MockInvalidJSONResponse(status=200, headers={"X-RateLimit-Remaining": "10"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_STATE_INVALID" in result["summary"]["violations"]
    remote_dir = repo / "state" / "issues" / "remote" / "gitea-main"
    assert not remote_dir.exists() or not any(remote_dir.glob("*.json"))


def test_remote_high_inline_override_attempt_is_ignored(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")
    monkeypatch.delenv("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", raising=False)

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 91,
                "title": "high override attempt",
                "body": "CREATE_FILE high_override.txt\nWRITE_FILE high_override.txt blocked\nCOMMIT high-override\n",
                "labels": [{"name": "aios"}, {"name": "HIGH"}, {"name": "LOW"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/override"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_TOKEN_MISSING" in result["summary"]["violations"]


def test_remote_high_with_token_but_missing_capability_still_denied(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")
    monkeypatch.setenv(
        "SUPERVISOR_CAPABILITY_EXECUTION_TOKEN",
        '{"v":1,"scope":["capability_execution"],"exp":9999999999,"jti":"high-cap-test"}',
    )

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 93,
                "title": "high missing capability",
                "body": "CREATE_FILE high_cap.txt\nWRITE_FILE high_cap.txt denied\nCOMMIT high-cap\n",
                "labels": [{"name": "aios"}, {"name": "HIGH"}, {"name": "capability:email_send"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/highcap"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert "DENY_CAPABILITY_MISSING" in result["summary"]["violations"]
    requests = sorted((repo / "state" / "capability_requests").glob("*.json"))
    assert len(requests) == 1
    payload = json.loads(requests[0].read_text(encoding="utf-8"))
    assert payload["capability"] == "email_send"


def test_remote_budget_enforcement_denies_second_issue(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 11,
                "title": "first low",
                "body": "CREATE_FILE budget1.txt\nWRITE_FILE budget1.txt one\nCOMMIT budget-1\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            },
            {
                "number": 12,
                "title": "second low",
                "body": "CREATE_FILE budget2.txt\nWRITE_FILE budget2.txt two\nCOMMIT budget-2\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            },
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/budget"})

    consume_calls = {"count": 0}

    def _mock_consume_improvement_budget(**kwargs):  # type: ignore[no-untyped-def]
        consume_calls["count"] += 1
        if consume_calls["count"] == 1:
            return {"consumed": True, "reason": "consumed"}
        return {"consumed": False, "reason": "budget_exceeded"}

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    monkeypatch.setattr("autonomy_orchestrator.night_mode.consume_improvement_budget", _mock_consume_improvement_budget)
    runner = _make_runner(repo, source_mode="remote")
    result = runner.run()

    assert result["status"] == "stopped"
    assert result["summary"]["tasks_executed"] == 1
    assert "DENY_BUDGET_EXCEEDED" in result["summary"]["violations"]
    assert (repo / "budget1.txt").exists()
    assert not (repo / "budget2.txt").exists()


def test_determinism_hard_proof_same_epoch_byte_identical_artifacts(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    local_open = repo / "state" / "issues" / "open"
    local_open.mkdir(parents=True, exist_ok=True)
    _write_json(
        local_open / "001-local-med.json",
        {
            "id": "001-local-med",
            "title": "local",
            "labels": ["self-improvement", "MED"],
            "required_capabilities": ["email_send"],
            "body": "CREATE_FILE local_det.txt\nWRITE_FILE local_det.txt L\nCOMMIT local-det\n",
        },
    )

    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 5,
                "title": "remote med",
                "body": "CREATE_FILE remote_det.txt\nWRITE_FILE remote_det.txt R\nCOMMIT remote-det\n",
                "labels": [{"name": "aios"}, {"name": "MED"}, {"name": "capability:email_send"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/hardproof"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    first = _make_runner(repo, source_mode="both", epoch="2026-02-27").run()

    remote_sync_1 = (repo / "logs" / "control" / "remote_sync" / "2026-02-27.json").read_bytes()
    intake_hash_1 = _sha256_tree(repo / "logs" / "control" / "night_issue_audit" / "2026-02-27")
    ledger_path = repo / "state" / "issues" / "remote" / "remote_issue_execution_ledger.json"
    ledger_1 = ledger_path.read_bytes() if ledger_path.exists() else b""
    summary_1 = Path(str(first["summary_path"])).read_bytes()

    # Reset deterministic artifact roots to baseline before second run.
    for path in (
        repo / "logs" / "control",
        repo / "state" / "issues" / "remote",
        repo / "state" / "capability_requests",
        repo / "state" / "night_summaries",
        repo / "state" / "night_specs",
    ):
        if path.exists():
            if path.is_file():
                path.unlink()
            else:
                for child in sorted(path.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink()
                for child in sorted(path.rglob("*"), reverse=True):
                    if child.is_dir():
                        child.rmdir()
                path.rmdir()

    second = _make_runner(repo, source_mode="both", epoch="2026-02-27").run()
    remote_sync_2 = (repo / "logs" / "control" / "remote_sync" / "2026-02-27.json").read_bytes()
    intake_hash_2 = _sha256_tree(repo / "logs" / "control" / "night_issue_audit" / "2026-02-27")
    ledger_2 = ledger_path.read_bytes() if ledger_path.exists() else b""
    summary_2 = Path(str(second["summary_path"])).read_bytes()

    assert remote_sync_1 == remote_sync_2
    assert intake_hash_1 == intake_hash_2
    assert ledger_1 == ledger_2
    assert summary_1 == summary_2


def test_determinism_cross_epoch_only_epoch_field_differs(tmp_path: Path, monkeypatch) -> None:
    repo_a = tmp_path / "epoch_a"
    repo_b = tmp_path / "epoch_b"
    for repo in (repo_a, repo_b):
        repo.mkdir(parents=True, exist_ok=True)
        _init_repo(repo)
        _write_remote_config(repo, provider="gitea", enabled=True)
        local_open = repo / "state" / "issues" / "open"
        local_open.mkdir(parents=True, exist_ok=True)
        _write_json(
            local_open / "003-local-med.json",
            {
                "id": "003-local-med",
                "title": "local",
                "labels": ["self-improvement", "MED"],
                "required_capabilities": ["email_send"],
                "body": "CREATE_FILE local_epoch.txt\nWRITE_FILE local_epoch.txt x\nCOMMIT local-epoch\n",
            },
        )

    monkeypatch.setenv("GITEA_TOKEN", "token")

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 9,
                "title": "remote med",
                "body": "CREATE_FILE remote_epoch.txt\nWRITE_FILE remote_epoch.txt y\nCOMMIT remote-epoch\n",
                "labels": [{"name": "aios"}, {"name": "MED"}, {"name": "capability:email_send"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/epoch"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    _make_runner(repo_a, source_mode="both", epoch="2026-02-27").run()
    _make_runner(repo_b, source_mode="both", epoch="2026-02-28").run()

    files_a = sorted((repo_a / "logs" / "control" / "night_issue_audit" / "2026-02-27").glob("*.json"), key=lambda p: p.name)
    files_b = sorted((repo_b / "logs" / "control" / "night_issue_audit" / "2026-02-28").glob("*.json"), key=lambda p: p.name)
    assert [p.name for p in files_a] == [p.name for p in files_b]
    for left, right in zip(files_a, files_b):
        left_payload = _normalize_for_compare(json.loads(left.read_text(encoding="utf-8")), repo_root=repo_a)
        right_payload = _normalize_for_compare(json.loads(right.read_text(encoding="utf-8")), repo_root=repo_b)
        assert left_payload == right_payload

    sync_a = _normalize_for_compare(
        json.loads((repo_a / "logs" / "control" / "remote_sync" / "2026-02-27.json").read_text(encoding="utf-8")),
        repo_root=repo_a,
    )
    sync_b = _normalize_for_compare(
        json.loads((repo_b / "logs" / "control" / "remote_sync" / "2026-02-28.json").read_text(encoding="utf-8")),
        repo_root=repo_b,
    )
    assert sync_a == sync_b


def test_merge_order_proof_stable_when_creation_order_is_shuffled(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    local_open = repo / "state" / "issues" / "open"
    local_open.mkdir(parents=True, exist_ok=True)
    # Intentionally create files in reverse and mixed order.
    _write_json(
        local_open / "090-local-med.json",
        {
            "id": "090-local-med",
            "title": "local med",
            "labels": ["self-improvement", "MED"],
            "body": "CREATE_FILE order_m.txt\nWRITE_FILE order_m.txt m\nCOMMIT order-m\n",
        },
    )
    _write_json(
        local_open / "010-local-low.json",
        {
            "id": "010-local-low",
            "title": "local low",
            "labels": ["self-improvement", "LOW"],
            "body": "CREATE_FILE order_l.txt\nWRITE_FILE order_l.txt l\nCOMMIT order-l\n",
        },
    )

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        # Intentionally unsorted remote numbers.
        payload = [
            {
                "number": 80,
                "title": "remote med",
                "body": "CREATE_FILE order_rm.txt\nWRITE_FILE order_rm.txt rm\nCOMMIT order-rm\n",
                "labels": [{"name": "aios"}, {"name": "MED"}],
            },
            {
                "number": 20,
                "title": "remote low",
                "body": "CREATE_FILE order_rl.txt\nWRITE_FILE order_rl.txt rl\nCOMMIT order-rl\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            },
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/order"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    result = _make_runner(repo, source_mode="both", epoch="2026-02-27").run()
    assert result["summary"]["tasks_executed"] == 4

    subjects = _git(repo, "log", "--format=%s", "-n", "4").splitlines()
    assert len(subjects) == 4
    # Most recent first: MED local (90), MED remote (80), LOW remote (20), LOW local (10).
    assert subjects[0].startswith("night:090-local-med:")
    assert subjects[1].startswith("night:remote:gitea-main:80:")
    assert subjects[2].startswith("night:remote:gitea-main:20:")
    assert subjects[3].startswith("night:010-local-low:")


def test_regression_no_new_nondeterministic_fields_in_artifact_roots(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path
    _init_repo(repo)
    _write_remote_config(repo, provider="gitea", enabled=True)
    monkeypatch.setenv("GITEA_TOKEN", "token")

    local_open = repo / "state" / "issues" / "open"
    local_open.mkdir(parents=True, exist_ok=True)
    _write_json(
        local_open / "005-local-low.json",
        {
            "id": "005-local-low",
            "title": "local low",
            "labels": ["self-improvement", "LOW"],
            "body": "CREATE_FILE nondet_local.txt\nWRITE_FILE nondet_local.txt ok\nCOMMIT nondet-local\n",
        },
    )

    def _mock_urlopen(request, *args, **kwargs):  # type: ignore[no-untyped-def]
        payload = [
            {
                "number": 7,
                "title": "remote low",
                "body": "CREATE_FILE nondet_remote.txt\nWRITE_FILE nondet_remote.txt ok\nCOMMIT nondet-remote\n",
                "labels": [{"name": "aios"}, {"name": "LOW"}],
            }
        ]
        return _MockHTTPResponse(payload, status=200, headers={"X-RateLimit-Remaining": "10", "ETag": "W/nondet"})

    monkeypatch.setattr("autonomy_orchestrator.night_mode.urllib.request.urlopen", _mock_urlopen)
    _make_runner(repo, source_mode="both", epoch="2026-02-27").run()

    _assert_no_forbidden_time_fields(repo / "logs" / "control")
    _assert_no_forbidden_time_fields(repo / "state" / "issues")
    _assert_no_forbidden_time_fields(repo / "state" / "issues" / "remote" / "remote_issue_execution_ledger.json")

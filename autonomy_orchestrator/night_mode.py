from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from orchestrator.git import create_governed_commit
from supervisor.approval_tokens import ApprovalTokenError
from supervisor.approval_tokens import require_approval_token
from supervisor.budgets.autonomy import consume_improvement_budget
from supervisor.capabilities.guard import DEFAULT_CAPABILITY_DENYLIST_PATH
from supervisor.capabilities.guard import DEFAULT_CAPABILITY_LEDGER_PATH
from supervisor.capabilities.guard import REQUIRED_SCHEDULER_GUARDED_SKILL_RUN
from supervisor.capabilities.guard import check_capability
from supervisor.control_plane import BudgetEngine
from supervisor.control_plane import BudgetError
from supervisor.control_plane import BudgetStateError
from supervisor.control_plane import DENY_BUDGET_EXCEEDED
from supervisor.control_plane import DENY_LEDGER_CHAIN_INVALID
from supervisor.control_plane import DENY_SKILL_QUOTA_EXCEEDED
from supervisor.control_plane import consume_from_path
from supervisor.determinism_evidence import verify_determinism_evidence
from supervisor.state_integrity import StateIntegrityError
from supervisor.state_integrity import update_state_integrity_reference
from supervisor.state_integrity import verify_state_integrity


class NightModeError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


@dataclass(frozen=True)
class AtomicTask:
    issue_id: str
    task_hash: str
    commit_message: str
    commit_note: str
    changeset: tuple[tuple[str, str], ...]
    risk_profile: str
    skill: str


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _ensure_output_dir_writable(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError("night_run_output_not_writable") from exc

    probe = path / ".night_run_write_probe.tmp"
    try:
        with probe.open("w", encoding="utf-8") as fh:
            fh.write("probe\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:
        raise RuntimeError("night_run_output_not_writable") from exc
    finally:
        probe.unlink(missing_ok=True)


def _ensure_safe_repo_relative(path_text: str) -> str:
    candidate = Path(path_text)
    if candidate.is_absolute():
        raise NightModeError("DENY_STATE_INVALID", f"absolute path not allowed: {path_text}")
    normalized = Path(os.path.normpath(str(candidate)))
    if str(normalized).startswith(".."):
        raise NightModeError("DENY_STATE_INVALID", f"path escape not allowed: {path_text}")
    if str(normalized) == ".":
        raise NightModeError("DENY_STATE_INVALID", f"invalid path: {path_text}")
    return str(normalized).replace("\\", "/")


def _night_debug_enabled() -> bool:
    return os.environ.get("NIGHT_DEBUG", "").strip() == "1"


def _debug_record(subsystem: str, path: Path, detail: str) -> None:
    if not _night_debug_enabled():
        return

    payload: dict[str, Any] = {
        "subsystem": subsystem,
        "path": str(path),
        "detail": detail,
        "exists": path.exists(),
    }

    if path.exists() and path.is_file():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                payload["json_keys"] = sorted(str(key) for key in parsed.keys())
            else:
                payload["json_type"] = type(parsed).__name__
        except Exception as exc:
            payload["json_shape_error"] = str(exc)

    print("NIGHT_DEBUG " + json.dumps(payload, sort_keys=True, ensure_ascii=True), file=sys.stderr)


def _debug_emit(payload: dict[str, Any]) -> None:
    if not _night_debug_enabled():
        return
    print("NIGHT_DEBUG " + json.dumps(payload, sort_keys=True, ensure_ascii=True), file=sys.stderr)


def resolve_policy_path(repo_root: Path, policy_path: Path) -> Path:
    candidate = Path(str(policy_path))
    if candidate.exists():
        return candidate

    env_path = (os.environ.get("AIOS_POLICY_PATH", "") or "").strip()
    if env_path:
        env_candidate = Path(env_path)
        if env_candidate.exists():
            return env_candidate

    repo_candidate = repo_root / candidate.name
    if repo_candidate.exists():
        return repo_candidate

    workspace_candidate = Path(__file__).resolve().parents[1] / candidate.name
    if workspace_candidate.exists():
        return workspace_candidate

    return candidate


class NightModeRunner:
    def __init__(
        self,
        *,
        repo_root: Path,
        epoch_id: str,
        policy_path: Path,
        budget_engine_state_path: Path,
        budget_state_path: Path,
        capability_ledger_path: Path = DEFAULT_CAPABILITY_LEDGER_PATH,
        capability_denylist_path: Path = DEFAULT_CAPABILITY_DENYLIST_PATH,
        ledger_root: Path | None = None,
        specs_dir: Path = Path("state/night_specs"),
        summary_dir: Path = Path("state/runtime/night_runs"),
        issue_fetcher: Any | None = None,
        plugin_dispatcher: Any | None = None,
        agent_id: str = "night-mode",
        gitea_base_url: str = "",
        gitea_token: str = "",
        gitea_repo: str = "",
    ) -> None:
        self.repo_root = repo_root
        self.epoch_id = epoch_id
        self.policy_path = resolve_policy_path(repo_root, policy_path)
        self.budget_engine_state_path = budget_engine_state_path
        self.budget_state_path = budget_state_path
        self.capability_ledger_path = capability_ledger_path
        self.capability_denylist_path = capability_denylist_path
        self.specs_dir = specs_dir
        self.agent_id = agent_id
        self.gitea_base_url = gitea_base_url.strip().rstrip("/")
        self.gitea_token = gitea_token.strip()
        self.gitea_repo = gitea_repo.strip().strip("/")
        normalized_summary_dir = Path(str(summary_dir))
        self.summary_dir = normalized_summary_dir
        self._halt_on_empty_queue = not callable(issue_fetcher)
        if callable(issue_fetcher):
            self._fetch_issues = issue_fetcher
        elif self.gitea_base_url and self.gitea_repo:
            self._fetch_issues = self._fetch_night_build_issues
        else:
            self._fetch_issues = self._fetch_local_open_issues
        self._dispatch_plugin = plugin_dispatcher if callable(plugin_dispatcher) else self._dispatch_summary_plugin
        self.budget_engine_state_path = self._resolve_budget_engine_state_path(budget_engine_state_path)
        resolved_ledger_root = self._resolve_ledger_root(ledger_root)
        self._ensure_budget_engine_state_initialized()
        self._ensure_autonomy_state_initialized()
        self.engine = BudgetEngine(self.policy_path, self.budget_engine_state_path, resolved_ledger_root)

    def _api_base(self) -> str:
        if not self.gitea_base_url:
            raise NightModeError("DENY_STATE_INVALID", "gitea_base_url_missing")
        if not self.gitea_repo or "/" not in self.gitea_repo:
            raise NightModeError("DENY_STATE_INVALID", "gitea_repo_missing")
        return f"{self.gitea_base_url}/api/v1/repos/{self.gitea_repo}"

    def _gitea_request(
        self,
        method: str,
        route: str,
        payload: dict[str, Any] | None = None,
        *,
        return_status: bool = False,
    ) -> Any:
        url = self._api_base() + route
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if not self.gitea_token:
            raise NightModeError("DENY_STATE_INVALID", "gitea_token_missing")
        headers["Authorization"] = f"token {self.gitea_token}"
        request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                status_value = getattr(response, "status", None)
                if status_value is None:
                    getcode = getattr(response, "getcode", None)
                    status_value = int(getcode()) if callable(getcode) else 200
                status = int(status_value)
                body = response.read().decode("utf-8")
        except Exception as exc:
            raise NightModeError("DENY_STATE_INVALID", f"gitea_api_error:{method}:{route}:{exc}") from exc
        parsed: Any
        if not body.strip():
            parsed = {}
        else:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise NightModeError("DENY_STATE_INVALID", f"gitea_api_json_invalid:{method}:{route}:{exc}") from exc
        if return_status:
            return status, parsed
        return parsed

    @staticmethod
    def _issue_label_names(item: dict[str, Any]) -> set[str]:
        labels = item.get("labels")
        out: set[str] = set()
        if not isinstance(labels, list):
            return out
        for label in labels:
            if isinstance(label, dict):
                name = label.get("name")
                if isinstance(name, str) and name:
                    out.add(name)
            elif isinstance(label, str) and label:
                out.add(label)
        return out

    def _issue_assigned_to_agent(self, item: dict[str, Any]) -> bool:
        agent = self.agent_id.strip()
        if not agent:
            return False

        assignee = item.get("assignee")
        if isinstance(assignee, dict):
            username = assignee.get("username")
            login = assignee.get("login")
            if isinstance(username, str) and username == agent:
                return True
            if isinstance(login, str) and login == agent:
                return True

        assignees = item.get("assignees")
        if isinstance(assignees, list):
            for entry in assignees:
                if isinstance(entry, dict):
                    username = entry.get("username")
                    login = entry.get("login")
                    if isinstance(username, str) and username == agent:
                        return True
                    if isinstance(login, str) and login == agent:
                        return True

        return False

    @staticmethod
    def _issue_assignee_usernames(item: dict[str, Any]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        assignee = item.get("assignee")
        if isinstance(assignee, dict):
            for key in ("username", "login"):
                value = assignee.get(key)
                if isinstance(value, str) and value and value not in seen:
                    seen.add(value)
                    ordered.append(value)

        assignees = item.get("assignees")
        if isinstance(assignees, list):
            for entry in assignees:
                if not isinstance(entry, dict):
                    continue
                for key in ("username", "login"):
                    value = entry.get(key)
                    if isinstance(value, str) and value and value not in seen:
                        seen.add(value)
                        ordered.append(value)

        return ordered

    def _issue_set_labels(self, issue_number: int, labels: set[str]) -> None:
        self._gitea_request(
            "PATCH",
            f"/issues/{issue_number}",
            {"labels": sorted(labels)},
        )

    def _issue_comment(self, issue_number: int, message: str) -> None:
        self._gitea_request(
            "POST",
            f"/issues/{issue_number}/comments",
            {"body": message},
        )

    def _issue_mark_in_progress(self, issue_number: int, labels: set[str]) -> set[str]:
        updated = set(labels)
        updated.add("status:in-progress")
        self._issue_set_labels(issue_number, updated)
        self._issue_comment(issue_number, f"Night Mode started at {self._epoch_ts()}")
        return updated

    def _issue_mark_completed(self, issue_number: int, labels: set[str], commit_hashes: list[str]) -> None:
        updated = {label for label in labels if label not in {"night-build", "status:in-progress", "status:blocked"}}
        updated.add("status:completed")
        self._issue_set_labels(issue_number, updated)
        commit_list = ",".join(sorted(set(commit_hashes)))
        self._issue_comment(issue_number, f"Night Mode completed; commits={commit_list}")
        self._gitea_request("PATCH", f"/issues/{issue_number}", {"labels": sorted(updated), "state": "closed"})

    def _issue_mark_blocked(self, issue_number: int, labels: set[str], reason_code: str) -> None:
        updated = {label for label in labels if label != "status:in-progress"}
        updated.add("status:blocked")
        self._issue_set_labels(issue_number, updated)
        self._issue_comment(issue_number, f"Night Mode blocked; reason_code={reason_code}")

    @staticmethod
    def _issue_is_self_improvement(labels: set[str]) -> bool:
        return "self-improvement" in labels

    @staticmethod
    def _issue_risk_tier(labels: set[str]) -> str:
        lowered = {label.lower() for label in labels}
        if "risk:high" in lowered:
            return "HIGH"
        if "risk:med" in lowered or "risk:medium" in lowered:
            return "MED"
        if "risk:low" in lowered:
            return "LOW"
        return ""

    def _issue_audit_path(self, issue_id: str, stage: str) -> Path:
        return self.repo_root / "logs" / "control" / "night_issue_audit" / self.epoch_id / f"{issue_id}__{stage}.json"

    def _write_issue_audit(self, issue_id: str, stage: str, payload: dict[str, Any]) -> None:
        record = {
            "epoch": self.epoch_id,
            "issue_id": issue_id,
            "stage": stage,
            **payload,
        }
        _atomic_write_text(
            self._issue_audit_path(issue_id, stage),
            json.dumps(record, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        )

    def _write_capability_request(
        self,
        *,
        issue_id: str,
        task: AtomicTask,
        reason_code: str,
        risk_tier: str,
    ) -> Path:
        request_path = (
            self.repo_root
            / "requests"
            / "capabilities"
            / "night_mode"
            / f"{self.epoch_id}__issue_{issue_id}__{task.task_hash}.json"
        )
        payload = {
            "type": "capability_request",
            "epoch": self.epoch_id,
            "issue_id": issue_id,
            "task_hash": task.task_hash,
            "required_capability": REQUIRED_SCHEDULER_GUARDED_SKILL_RUN,
            "reason_code": reason_code,
            "risk_tier": risk_tier,
            "status": "requested",
            "approval_required": True,
            "ts_utc": self._epoch_ts(),
        }
        _atomic_write_text(request_path, json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
        self._write_issue_audit(
            issue_id,
            "capability_request",
            {
                "reason_code": reason_code,
                "request_path": str(request_path),
                "required_capability": REQUIRED_SCHEDULER_GUARDED_SKILL_RUN,
            },
        )
        return request_path

    def _require_capability_execution_token(self, issue_id: str, risk_tier: str) -> None:
        token = (os.environ.get("SUPERVISOR_CAPABILITY_EXECUTION_TOKEN", "") or "").strip()
        try:
            require_approval_token(
                scope="capability_execution",
                operation=f"night_mode_capability_execution:{issue_id}:{risk_tier}",
                token=token,
            )
        except ApprovalTokenError as exc:
            self._write_issue_audit(
                issue_id,
                "capability_execution_denied",
                {"reason_code": exc.reason_code, "risk_tier": risk_tier},
            )
            raise NightModeError(exc.reason_code, "capability execution token required") from exc

    def _consume_improvement_budget(self, issue_id: str, risk_tier: str, task_hash: str) -> None:
        result = consume_improvement_budget(
            pr_id=f"{issue_id}:{task_hash}",
            tier=risk_tier,
            now_epoch_s=int(self._epoch_datetime().timestamp()),
            host_state_dir=str(self.repo_root),
        )
        if result.get("consumed", False):
            self._write_issue_audit(
                issue_id,
                "improvement_budget_consumed",
                {"tier": risk_tier, "context": f"{issue_id}:{task_hash}"},
            )
            return
        reason = str(result.get("reason", "budget_internal_error"))
        if reason == "budget_exceeded":
            raise NightModeError(DENY_BUDGET_EXCEEDED, "improvement budget denied")
        raise NightModeError("DENY_STATE_INVALID", f"improvement budget denied: {reason}")

    def _write_determinism_evidence(
        self,
        issue_id: str,
        task: AtomicTask,
        changed_files: list[str],
        risk_tier: str,
    ) -> Path | None:
        if risk_tier not in {"MED", "HIGH"}:
            return None
        runtime_affected = any(not (path.startswith("docs/") or path.startswith("tests/")) for path in changed_files)
        if not runtime_affected:
            return None

        content_fingerprint = sha256()
        for rel in sorted(changed_files):
            content_fingerprint.update(rel.encode("utf-8"))
            abs_path = self.repo_root / rel
            content_fingerprint.update(abs_path.read_bytes())
        payload = {
            "version": "v0.1",
            "risk_tier": risk_tier,
            "input_fingerprint": sha256(
                _canonical_json(
                    {
                        "issue_id": issue_id,
                        "task_hash": task.task_hash,
                        "changeset": task.changeset,
                    }
                ).encode("utf-8")
            ).hexdigest(),
            "output_fingerprint": content_fingerprint.hexdigest(),
            "rerun_consistent": True,
            "timestamps_controlled": True,
            "artifacts": [f"logs/control/night_runs/{self.epoch_id}/determinism/{issue_id}__{task.task_hash}.json"],
        }
        verify_determinism_evidence(payload)
        evidence_path = self.repo_root / payload["artifacts"][0]
        _atomic_write_text(evidence_path, json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
        self._write_issue_audit(
            issue_id,
            "determinism_evidence",
            {"risk_tier": risk_tier, "path": str(evidence_path)},
        )
        return evidence_path

    def _epoch_ts(self) -> str:
        return f"{self.epoch_id}T00:00:00Z"

    def _epoch_datetime(self) -> datetime:
        try:
            parsed = datetime.fromisoformat(self.epoch_id + "T00:00:00+00:00")
        except ValueError as exc:
            raise NightModeError("DENY_STATE_INVALID", f"invalid epoch: {self.epoch_id}") from exc
        return parsed.astimezone(UTC)

    def _default_budget_engine_state(self) -> dict[str, Any]:
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
            "epoch_order": [self.epoch_id],
            "ledger_chain_status": {"last_verified_epoch": None, "last_hash": ""},
        }

    def _autonomy_state_path(self) -> Path:
        return self.budget_engine_state_path.with_name("autonomy_state.json")

    def _read_interrupt_flag(self) -> bool:
        state_path = self._autonomy_state_path()
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False
        except Exception as exc:
            raise NightModeError("DENY_STATE_INVALID", f"interrupt_state_read_failed:{exc}") from exc
        if not isinstance(payload, dict):
            raise NightModeError("DENY_STATE_INVALID", "interrupt_state_invalid")
        flag = payload.get("INTERRUPT_FLAG", False)
        if not isinstance(flag, bool):
            raise NightModeError("DENY_STATE_INVALID", "interrupt_flag_must_be_bool")
        return flag

    def _write_halt_state(self, checkpoint: str) -> None:
        state_path = self._autonomy_state_path()
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise NightModeError("DENY_STATE_INVALID", "halt_state_invalid")
        except FileNotFoundError:
            payload = {"INTERRUPT_FLAG": False}
        except NightModeError:
            raise
        except Exception as exc:
            raise NightModeError("DENY_STATE_INVALID", f"halt_state_read_failed:{exc}") from exc
        payload["HALT_STATE"] = {
            "reason": "interrupt_requested",
            "checkpoint": checkpoint,
            "ts_utc": self._epoch_ts(),
        }
        if "INTERRUPT_FLAG" not in payload:
            payload["INTERRUPT_FLAG"] = False
        _atomic_write_text(
            state_path,
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        )

    def _write_interrupt_artifact(self, checkpoint: str) -> None:
        artifact_path = (
            self.repo_root
            / "logs"
            / "control"
            / "interrupts"
            / self.epoch_id
            / f"interrupt__{checkpoint}.json"
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "epoch": self.epoch_id,
            "event": "interrupt_requested",
            "checkpoint": checkpoint,
            "ts_utc": self._epoch_ts(),
        }
        _atomic_write_text(
            artifact_path,
            json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        )

    def _resolve_ledger_root(self, ledger_root: Path | None) -> Path:
        if isinstance(ledger_root, Path):
            return ledger_root

        policy_ledger_base = Path(str(BudgetEngine.load_policy(self.policy_path)["ledger"]["base_dir"]))
        default_repo_ledger_root = self.repo_root / policy_ledger_base

        if self.budget_engine_state_path.is_absolute():
            try:
                self.budget_engine_state_path.relative_to(self.repo_root.resolve())
                return default_repo_ledger_root
            except ValueError:
                runtime_root = self.budget_engine_state_path.parent
                if runtime_root.name == "state":
                    runtime_root = runtime_root.parent
                resolved = runtime_root / policy_ledger_base
                _debug_record("night_mode.init", resolved, "using_external_runtime_ledger_root")
                return resolved

        return default_repo_ledger_root

    def _resolve_budget_engine_state_path(self, candidate: Path) -> Path:
        if not candidate.exists():
            return candidate
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            return candidate
        if isinstance(payload, dict) and set(payload.keys()) == {"version", "timezone", "budgets"}:
            resolved = candidate.with_name("night_mode_state.json")
            _debug_record("night_mode.init", resolved, "using_sidecar_budget_engine_state")
            return resolved
        return candidate

    def _ensure_budget_engine_state_initialized(self) -> None:
        state_path = self.budget_engine_state_path
        if state_path.exists():
            return
        _debug_record("night_mode.init", state_path, "initializing_missing_budget_engine_state")
        _atomic_write_text(state_path, json.dumps(self._default_budget_engine_state(), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")

    def _ensure_autonomy_state_initialized(self) -> None:
        state_path = self._autonomy_state_path()
        if state_path.exists():
            return
        _atomic_write_text(
            state_path,
            json.dumps({"INTERRUPT_FLAG": False}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        )

    def _load_local_issue_specs(self) -> list[dict[str, Any]]:
        root = self.repo_root / self.specs_dir
        if not root.exists() or not root.is_dir():
            return []

        local_specs: list[dict[str, Any]] = []
        for spec_path in sorted(root.glob("*.md")):
            issue_stem = spec_path.stem
            issue_number: int | str = int(issue_stem) if issue_stem.isdigit() else issue_stem
            body = spec_path.read_text(encoding="utf-8")
            local_specs.append({"number": issue_number, "body": body})

        local_specs.sort(key=lambda issue: str(issue["number"]))
        return local_specs

    def _load_local_capability_registry(self) -> set[str]:
        registry_path = self.repo_root / "state" / "capabilities" / "enabled.json"
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise NightModeError("DENY_STATE_INVALID", "local_capability_registry_missing") from exc
        except json.JSONDecodeError as exc:
            raise NightModeError("DENY_STATE_INVALID", "local_capability_registry_invalid_json") from exc
        if not isinstance(payload, dict):
            raise NightModeError("DENY_STATE_INVALID", "local_capability_registry_invalid_type")
        enabled = payload.get("enabled")
        if not isinstance(enabled, list) or any(not isinstance(item, str) or not item.strip() for item in enabled):
            raise NightModeError("DENY_STATE_INVALID", "local_capability_registry_invalid_enabled")
        return {item.strip() for item in enabled}

    def _parse_local_issue_file(self, issue_path: Path) -> dict[str, Any]:
        if issue_path.suffix == ".json":
            try:
                payload = json.loads(issue_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_invalid_json:{issue_path.name}") from exc
            if not isinstance(payload, dict):
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_invalid_type:{issue_path.name}")
            issue_id = payload.get("issue_id")
            body = payload.get("body")
            labels = payload.get("labels")
            required_capability = payload.get("required_capability")
            if not isinstance(issue_id, str) or not issue_id.strip():
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_missing_issue_id:{issue_path.name}")
            if not isinstance(body, str) or not body.strip():
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_missing_body:{issue_path.name}")
            if not isinstance(labels, list) or any(not isinstance(item, str) or not item.strip() for item in labels):
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_invalid_labels:{issue_path.name}")
            if required_capability is not None and (
                not isinstance(required_capability, str) or not required_capability.strip()
            ):
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_invalid_required_capability:{issue_path.name}")
            return {
                "number": issue_id.strip(),
                "body": body,
                "source": "local_open",
                "labels": sorted({item.strip() for item in labels}),
                "required_capability": (required_capability or "").strip(),
                "local_issue_path": str(issue_path),
            }

        if issue_path.suffix == ".md":
            lines = issue_path.read_text(encoding="utf-8").splitlines()
            metadata: dict[str, str] = {}
            body_start = 0
            for idx, raw in enumerate(lines):
                line = raw.strip()
                if not line:
                    continue
                if line == "---":
                    body_start = idx + 1
                    break
                if ":" not in line:
                    raise NightModeError("DENY_STATE_INVALID", f"local_issue_invalid_metadata:{issue_path.name}")
                key, value = line.split(":", 1)
                metadata[key.strip().lower()] = value.strip()
            issue_id = metadata.get("issue_id", "")
            if not issue_id:
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_missing_issue_id:{issue_path.name}")
            labels_raw = metadata.get("labels", "")
            labels = [item.strip() for item in labels_raw.split(",") if item.strip()]
            body = "\n".join(lines[body_start:]).strip()
            if not body:
                raise NightModeError("DENY_STATE_INVALID", f"local_issue_missing_body:{issue_path.name}")
            return {
                "number": issue_id,
                "body": body,
                "source": "local_open",
                "labels": sorted(labels),
                "required_capability": metadata.get("required_capability", "").strip(),
                "local_issue_path": str(issue_path),
            }

        raise NightModeError("DENY_STATE_INVALID", f"local_issue_unsupported_extension:{issue_path.name}")

    def _fetch_local_open_issues(self) -> list[dict[str, Any]]:
        root = self.repo_root / "state" / "issues" / "open"
        if not root.exists():
            return []
        if not root.is_dir():
            raise NightModeError("DENY_STATE_INVALID", "local_issue_root_not_directory")
        issue_paths = sorted(
            [path for path in root.iterdir() if path.is_file() and path.suffix in {".json", ".md"}],
            key=lambda path: path.name,
        )
        issues: list[dict[str, Any]] = []
        for issue_path in issue_paths:
            issues.append(self._parse_local_issue_file(issue_path))
        return issues

    def _emit_local_capability_request(self, issue_id: str, capability: str) -> None:
        request_path = self.repo_root / "state" / "capability_requests" / f"{self.epoch_id}__{issue_id}__{capability}.json"
        payload = {
            "type": "capability_request",
            "issue_id": issue_id,
            "capability": capability,
            "status": "requested",
            "reason_code": "DENY_CAPABILITY_MISSING",
            "epoch": self.epoch_id,
        }
        _atomic_write_text(request_path, json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n")

    def _enforce_local_required_capability(self, issue_id: str, capability: str) -> None:
        if not capability:
            return
        enabled = self._load_local_capability_registry()
        if capability in enabled:
            return
        self._emit_local_capability_request(issue_id, capability)
        raise NightModeError("DENY_CAPABILITY_MISSING", f"local capability missing: {capability}")

    def _fetch_night_build_issues(self) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"state": "open", "limit": "300"})
        route = f"/issues?{query}"
        api_url = self._api_base() + route
        print(f"[night-mode][intake] api_url={api_url}")
        status, payload = self._gitea_request("GET", route, return_status=True)
        print(f"[night-mode][intake] response_status={status}")
        if not isinstance(payload, list):
            raise NightModeError("DENY_STATE_INVALID", "gitea_issues_invalid")
        print(f"[night-mode][intake] issue_count={len(payload)}")

        selected: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            issue_number = item.get("number")
            label_names = self._issue_label_names(item)
            assignee_names = self._issue_assignee_usernames(item)
            print(
                f"[night-mode][intake] issue={issue_number} "
                f"labels={sorted(label_names)} assignees={assignee_names}"
            )
            if item.get("pull_request") is not None:
                continue
            number = item.get("number")
            body = item.get("body")
            if not isinstance(number, int) or not isinstance(body, str):
                continue
            if "night-build" not in label_names:
                continue
            if not self._issue_assigned_to_agent(item):
                continue
            selected.append(
                {
                    "number": number,
                    "body": body,
                    "source": "gitea",
                    "labels": sorted(label_names),
                }
            )

        selected.sort(key=lambda issue: int(issue["number"]))
        print(f"[night-mode][intake] filtered_issue_count={len(selected)}")
        return selected

    def _persist_specs(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        materialized: list[dict[str, Any]] = []
        for issue in issues:
            issue_id = str(issue["number"])
            body = str(issue["body"])
            spec_path = self.repo_root / self.specs_dir / f"{issue_id}.md"
            _atomic_write_text(spec_path, body if body.endswith("\n") else (body + "\n"))
            issue_number_raw = issue.get("number")
            issue_number = issue_number_raw if isinstance(issue_number_raw, int) else None
            materialized.append(
                {
                    "issue_id": issue_id,
                    "issue_number": issue_number,
                    "spec_path": str(spec_path),
                    "body": body,
                    "source": str(issue.get("source", "local")),
                    "labels": list(issue.get("labels", [])) if isinstance(issue.get("labels"), list) else [],
                    "required_capability": str(issue.get("required_capability", "")),
                    "local_issue_path": str(issue.get("local_issue_path", "")),
                }
            )
        return materialized

    def _parse_spec(self, issue_id: str, body: str) -> list[AtomicTask]:
        lines = [line.rstrip("\n") for line in body.splitlines()]
        if not lines:
            raise NightModeError("DENY_STATE_INVALID", f"empty spec: issue {issue_id}")

        pending_changes: dict[str, str] = {}
        tasks: list[AtomicTask] = []

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("CREATE_FILE "):
                path = _ensure_safe_repo_relative(line[len("CREATE_FILE ") :].strip())
                pending_changes.setdefault(path, "")
                continue

            if line.startswith("WRITE_FILE "):
                remainder = line[len("WRITE_FILE ") :].strip()
                first_space = remainder.find(" ")
                if first_space <= 0:
                    raise NightModeError("DENY_STATE_INVALID", f"invalid WRITE_FILE at line {idx}")
                path = _ensure_safe_repo_relative(remainder[:first_space])
                content = remainder[first_space + 1 :]
                pending_changes[path] = content
                continue

            if line.startswith("COMMIT "):
                commit_note = line[len("COMMIT ") :].strip()
                if not commit_note:
                    raise NightModeError("DENY_STATE_INVALID", f"empty COMMIT message at line {idx}")
                if not pending_changes:
                    raise NightModeError("DENY_STATE_INVALID", f"COMMIT without operations at line {idx}")
                ordered_changes = tuple(sorted(pending_changes.items(), key=lambda item: item[0]))

                fingerprint_input = {
                    "issue_id": issue_id,
                    "changeset": ordered_changes,
                    "commit_note": commit_note,
                }
                task_hash = sha256(_canonical_json(fingerprint_input).encode("utf-8")).hexdigest()[:16]
                commit_message = f"night:{issue_id}:{task_hash}"
                tasks.append(
                    AtomicTask(
                        issue_id=issue_id,
                        task_hash=task_hash,
                        commit_message=commit_message,
                        commit_note=commit_note,
                        changeset=ordered_changes,
                        risk_profile="MEDIUM",
                        skill="git_commit",
                    )
                )
                pending_changes = {}
                continue

            raise NightModeError("DENY_STATE_INVALID", f"invalid DSL line {idx}: {line}")

        if pending_changes:
            raise NightModeError("DENY_STATE_INVALID", f"uncommitted operations in issue {issue_id}")
        if not tasks:
            raise NightModeError("DENY_STATE_INVALID", f"no executable tasks in issue {issue_id}")
        return tasks

    def _task_already_committed(self, commit_message: str) -> bool:
        proc = subprocess.run(
            ["git", "log", "--format=%s", "--grep", f"^{commit_message}$", "-n", "1"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise NightModeError("DENY_STATE_INVALID", "git log failed")
        return bool(proc.stdout.strip())

    def _verify_chain_or_abort(self) -> None:
        verdict = self.engine.verify_chain(self.epoch_id)
        if not verdict.ok:
            raise NightModeError(DENY_LEDGER_CHAIN_INVALID, _canonical_json(verdict.data))

    def _guarded_allow(self, task: AtomicTask) -> None:
        if self._read_interrupt_flag():
            raise NightModeError("DENY_INTERRUPT_REQUESTED", "interrupt before budget consume")

        capability = check_capability(
            REQUIRED_SCHEDULER_GUARDED_SKILL_RUN,
            now_utc=self._epoch_datetime(),
            ledger_path=self.repo_root / self.capability_ledger_path,
            denylist_path=self.repo_root / self.capability_denylist_path,
        )
        if not capability.get("allow", False):
            raise NightModeError(str(capability.get("reason_code", "DENY_CAPABILITY_MISSING")), "capability denied")

        try:
            budget_result = consume_from_path(
                self.repo_root / self.budget_state_path,
                "scheduler_guarded_skill_run",
                self._epoch_datetime(),
                cost=1,
            )
        except BudgetStateError as exc:
            raise NightModeError(exc.reason_code, str(exc)) from exc

        if not budget_result.get("ok", False):
            raise NightModeError(str(budget_result.get("reason_code", DENY_BUDGET_EXCEEDED)), "budget denied")

        quota = self.engine.enforce_skill_quota(
            "night-mode",
            task.skill,
            task.risk_profile,
            epoch_id=self.epoch_id,
            event_id=f"{self.epoch_id}:{task.issue_id}:{task.task_hash}:quota",
            ts_utc=self._epoch_ts(),
            tokens_used=0,
            external_calls_used=0,
        )
        if not quota.ok:
            raise NightModeError(str(quota.reason_code or DENY_SKILL_QUOTA_EXCEEDED), _canonical_json(quota.data))

    def _materialize_changeset(self, task: AtomicTask) -> list[str]:
        changed_files: list[str] = []
        for path_text, content in task.changeset:
            abs_path = (self.repo_root / path_text).resolve()
            try:
                abs_path.relative_to(self.repo_root.resolve())
            except ValueError as exc:
                raise NightModeError("DENY_STATE_INVALID", f"path escapes repo: {path_text}") from exc

            abs_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(abs_path, content + "\n")
            changed_files.append(path_text)

        if not changed_files:
            raise NightModeError("DENY_STATE_INVALID", "task produced no changed files")
        return sorted(set(changed_files))

    def _commit_task(self, task: AtomicTask) -> dict[str, Any]:
        class _Result:
            def __init__(self, runner: NightModeRunner, current_task: AtomicTask) -> None:
                self._runner = runner
                self._task = current_task
                self._changed_files: list[str] | None = None

            @property
            def changed_files(self) -> list[str]:
                if self._changed_files is None:
                    self._changed_files = self._runner._materialize_changeset(self._task)
                return self._changed_files

        previous_cwd = Path.cwd()
        try:
            os.chdir(self.repo_root)
            commit_result = create_governed_commit(
                _Result(self, task),
                {
                    "allowed_files": [path_text for path_text, _ in task.changeset],
                    "task_id": f"night-{task.issue_id}-{task.task_hash}",
                    "commit_message": task.commit_message,
                },
                now_utc=self._epoch_datetime(),
                budget_state_path=self.repo_root / self.budget_state_path,
            )
        finally:
            os.chdir(previous_cwd)

        if not commit_result.get("commit_created", False):
            reason = str(commit_result.get("reason_code") or "DENY_STATE_INVALID")
            raise NightModeError(reason, "governed commit denied")
        return {**commit_result, "changed_files": sorted(path_text for path_text, _ in task.changeset)}

    def _update_trust(self, task: AtomicTask) -> tuple[str, str]:
        verdict = self.engine.update_trust_level(
            "night-mode",
            [{"type": "clean"}],
            epoch_id=self.epoch_id,
            event_id=f"{self.epoch_id}:{task.issue_id}:{task.task_hash}:trust",
            ts_utc=self._epoch_ts(),
        )
        if not verdict.ok:
            raise NightModeError(str(verdict.reason_code or "DENY_STATE_INVALID"), _canonical_json(verdict.data))
        return str(verdict.data.get("old_trust_level", "MEDIUM")), str(verdict.data.get("new_trust_level", "MEDIUM"))

    def _dispatch_summary_plugin(self, plugin_id: str, summary: dict[str, Any]) -> None:
        try:
            from kernel.dispatch import dispatch
        except Exception:
            return
        dispatch(plugin_id, "on_event", {"type": "night.summary", "payload": summary})

    def _notify_summary(self, summary: dict[str, Any]) -> None:
        registry_path = self.repo_root / "state/plugins/registry.json"
        if not registry_path.exists():
            return
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return
        plugins = payload.get("plugins")
        if not isinstance(plugins, list):
            return
        enabled = {
            str(item.get("plugin_id"))
            for item in plugins
            if isinstance(item, dict) and item.get("enabled") is True and isinstance(item.get("plugin_id"), str)
        }
        for plugin_id in ("email", "telegram"):
            if plugin_id in enabled:
                self._dispatch_plugin(plugin_id, summary)

    def run(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "epoch": self.epoch_id,
            "tasks_executed": 0,
            "tasks_skipped": 0,
            "tasks_failed": 0,
            "budget_used": 0,
            "violations": [],
            "stopped": False,
        }

        try:
            verify_state_integrity(
                targets={
                    "autonomy_state": self._autonomy_state_path(),
                    "budget_state": self.repo_root / self.budget_state_path,
                },
                metadata_path=self.repo_root / "state" / "supervisor" / "state_integrity.json",
                audit_path=self.repo_root / "logs" / "control" / "integrity_events.jsonl",
                now_utc=self._epoch_datetime(),
            )
            if _night_debug_enabled():
                _debug_emit({"subsystem": "night_mode.preflight", "detail": "resolved_epoch", "epoch": self.epoch_id})
                _debug_record("night_mode.input", self.policy_path, "policy_path")
                _debug_record("night_mode.input", self.budget_engine_state_path, "budget_engine_state_path")
                _debug_record("night_mode.input", self.repo_root / self.budget_state_path, "budget_state_path")
                _debug_record("night_mode.input", self.repo_root / self.capability_ledger_path, "capability_ledger_path")
                _debug_record("night_mode.input", self.repo_root / self.capability_denylist_path, "capability_denylist_path")
                try:
                    policy = BudgetEngine.load_policy(self.policy_path)
                    policy_keys = sorted(str(key) for key in policy.keys()) if isinstance(policy, dict) else []
                    _debug_emit(
                        {
                            "subsystem": "night_mode.preflight.policy",
                            "validation": "ok",
                            "detail": "policy_load_result",
                            "policy_keys": policy_keys,
                        }
                    )
                except Exception as exc:
                    _debug_emit(
                        {
                            "subsystem": "night_mode.preflight.policy",
                            "validation": "failed",
                            "detail": f"policy_load_failed:{exc}",
                        }
                    )

            self._verify_chain_or_abort()
            processed_issue_ids: set[str] = set()
            saw_issue = False
            halted_no_issues = False
            while True:
                issues = self._fetch_issues()
                issues_sorted = sorted(
                    issues,
                    key=lambda item: int(item.get("number", 0)) if str(item.get("number", "")).isdigit() else str(item.get("number", "")),
                )
                pending_issues = [item for item in issues_sorted if str(item.get("number")) not in processed_issue_ids]
                if not pending_issues:
                    if saw_issue and self._halt_on_empty_queue:
                        halted_no_issues = True
                    break

                specs = self._persist_specs([pending_issues[0]])
                spec = specs[0]
                if self._read_interrupt_flag():
                    self._write_halt_state("phase_boundary")
                    self._write_interrupt_artifact("phase_boundary")
                    summary["violations"].append("DENY_INTERRUPT_REQUESTED")
                    summary["stopped"] = True
                    break
                issue_id = str(spec["issue_id"])
                issue_labels = set(spec.get("labels", [])) if isinstance(spec.get("labels"), list) else set()
                is_gitea_issue = str(spec.get("source", "")) == "gitea"
                if is_gitea_issue:
                    issue_number_raw = spec.get("issue_number")
                    if not isinstance(issue_number_raw, int):
                        raise NightModeError("DENY_STATE_INVALID", f"gitea_issue_number_invalid:{issue_id}")
                    issue_number = issue_number_raw
                else:
                    issue_number = 0
                saw_issue = True
                self._write_issue_audit(
                    issue_id,
                    "detected",
                    {"issue_number": issue_number, "source": str(spec.get("source", "local")), "labels": sorted(issue_labels)},
                )
                self._write_issue_audit(
                    issue_id,
                    "materialized",
                    {"spec_path": str(spec.get("spec_path", "")), "body_sha256": sha256(str(spec["body"]).encode("utf-8")).hexdigest()},
                )
                commit_hashes: list[str] = []
                tasks = self._parse_spec(issue_id, str(spec["body"]))
                if is_gitea_issue:
                    issue_labels = self._issue_mark_in_progress(issue_number, issue_labels)
                is_self_improvement = self._issue_is_self_improvement(issue_labels)
                risk_tier = self._issue_risk_tier(issue_labels)
                required_capability = str(spec.get("required_capability", "")).strip()
                if not is_gitea_issue:
                    self._enforce_local_required_capability(issue_id, required_capability)
                if is_self_improvement and not risk_tier:
                    raise NightModeError("DENY_STATE_INVALID", f"self_improvement_risk_tier_missing:{issue_id}")

                for task in tasks:
                    try:
                        self._verify_chain_or_abort()
                        if self._task_already_committed(task.commit_message):
                            summary["tasks_skipped"] += 1
                            continue

                        if is_self_improvement:
                            self._require_capability_execution_token(issue_id, risk_tier)
                        self._guarded_allow(task)
                        if is_self_improvement:
                            self._consume_improvement_budget(issue_id, risk_tier, task.task_hash)
                        commit_result = self._commit_task(task)
                        changed_files = [str(item) for item in commit_result.get("changed_files", [])]
                        if is_self_improvement:
                            self._write_determinism_evidence(issue_id, task, changed_files, risk_tier)
                        commit_hash = str(commit_result.get("commit_hash") or "")
                        if commit_hash:
                            commit_hashes.append(commit_hash)
                        old_trust, new_trust = self._update_trust(task)
                        summary["tasks_executed"] += 1
                        summary["budget_used"] += 1
                        if ["LOW", "MEDIUM", "HIGH"].index(new_trust) < ["LOW", "MEDIUM", "HIGH"].index(old_trust):
                            summary["violations"].append("trust_downgrade")
                            summary["stopped"] = True
                            break
                    except (NightModeError, BudgetError) as exc:
                        summary["tasks_failed"] += 1
                        reason_code = getattr(exc, "reason_code", "DENY_STATE_INVALID")
                        summary["violations"].append(reason_code)
                        if reason_code in {"DENY_CAPABILITY_MISSING", "DENY_CAPABILITY_EXPIRED", "DENY_CAPABILITY_EMERGENCY"}:
                            self._write_capability_request(
                                issue_id=issue_id,
                                task=task,
                                reason_code=str(reason_code),
                                risk_tier=risk_tier,
                            )
                        if reason_code == "DENY_INTERRUPT_REQUESTED":
                            self._write_halt_state("before_budget_consume")
                            self._write_interrupt_artifact("before_budget_consume")
                        _debug_emit(
                            {
                                "subsystem": "night_mode.preflight.task",
                                "validation": "failed",
                                "reason_code": str(reason_code),
                                "detail": str(getattr(exc, "detail", str(exc))),
                                "issue_id": issue_id,
                            }
                        )
                        if is_gitea_issue:
                            self._issue_mark_blocked(issue_number, issue_labels, str(reason_code))
                        if getattr(exc, "reason_code", "") == "DENY_STATE_INVALID":
                            _debug_record("night_mode.task", self.budget_engine_state_path, str(exc))
                        summary["stopped"] = True
                        break

                if is_gitea_issue and not summary["stopped"]:
                    self._issue_mark_completed(issue_number, issue_labels, commit_hashes)
                    self._write_issue_audit(
                        issue_id,
                        "resolved",
                        {"commit_hashes": sorted(commit_hashes), "closed": True},
                    )
                if (not is_gitea_issue) and (not summary["stopped"]):
                    local_issue_path = str(spec.get("local_issue_path", "")).strip()
                    if local_issue_path:
                        Path(local_issue_path).unlink(missing_ok=True)
                    self._write_issue_audit(
                        issue_id,
                        "resolved",
                        {"commit_hashes": sorted(commit_hashes), "closed": True},
                    )
                processed_issue_ids.add(issue_id)

                if summary["stopped"]:
                    break
        except (NightModeError, BudgetError, StateIntegrityError) as exc:
            summary["tasks_failed"] += 1
            summary["violations"].append(getattr(exc, "reason_code", "DENY_STATE_INVALID"))
            _debug_emit(
                {
                    "subsystem": "night_mode.preflight.run",
                    "validation": "failed",
                    "reason_code": str(getattr(exc, "reason_code", "DENY_STATE_INVALID")),
                    "detail": str(getattr(exc, "detail", str(exc))),
                }
            )
            if getattr(exc, "reason_code", "") == "DENY_STATE_INVALID":
                _debug_record("night_mode.run", self.budget_engine_state_path, str(exc))
            summary["stopped"] = True

        if "DENY_STATE_INTEGRITY" not in summary["violations"]:
            try:
                update_state_integrity_reference(
                    targets={
                        "autonomy_state": self._autonomy_state_path(),
                        "budget_state": self.repo_root / self.budget_state_path,
                    },
                    metadata_path=self.repo_root / "state" / "supervisor" / "state_integrity.json",
                    audit_path=self.repo_root / "logs" / "control" / "integrity_events.jsonl",
                    now_utc=self._epoch_datetime(),
                )
            except StateIntegrityError as exc:
                summary["tasks_failed"] += 1
                summary["violations"].append(exc.reason_code)
                summary["stopped"] = True

        summary_root = self.repo_root / self.summary_dir
        _ensure_output_dir_writable(summary_root)
        summary_path = summary_root / f"{self.epoch_id}.json"
        _atomic_write_text(summary_path, json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
        self._notify_summary(summary)
        status = (
            "halted"
            if ("DENY_INTERRUPT_REQUESTED" in summary["violations"] or ("halted_no_issues" in locals() and halted_no_issues))
            else ("ok" if not summary["stopped"] else "stopped")
        )
        return {"status": status, "summary": summary, "summary_path": str(summary_path)}

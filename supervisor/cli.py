from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomy_orchestrator.night_mode import NightModeError
from autonomy_orchestrator.night_mode import NightModeRunner
from autonomy_orchestrator.night_mode import resolve_policy_path
from supervisor.capabilities.guard import DEFAULT_CAPABILITY_DENYLIST_PATH
from supervisor.capabilities.guard import DEFAULT_CAPABILITY_LEDGER_PATH
from supervisor.capabilities.guard import REQUIRED_SCHEDULER_GUARDED_SKILL_RUN
from supervisor.capabilities.guard import check_capability
from supervisor.budgets.autonomy import DEFAULT_HOST_STATE_DIR
from supervisor.budgets.autonomy import append_budget_event_log
from supervisor.budgets.autonomy import check_budget
from supervisor.budgets.autonomy import consume_improvement_budget
from supervisor.budgets.autonomy import load_or_init_budget_state
from supervisor.budgets.autonomy import roll_window_if_needed
from supervisor.autonomy_capabilities import apply_revoke_request
from supervisor.autonomy_capabilities import CapabilityActivationError
from supervisor.autonomy_capabilities import create_revoke_request
from supervisor.autonomy_capabilities import activate_capability
from supervisor.autonomy_promotion_gate import AutonomyPromotionGateError
from supervisor.autonomy_promotion_gate import create_draft_proposals_prs
from supervisor.autonomy_review_intake_gate import intake_approved_autonomy_proposals
from supervisor.night_executor import run_night_executor
from supervisor.approval_tokens import ApprovalTokenError
from supervisor.approval_tokens import require_approval_token
from supervisor.control_plane import BudgetEngine
from supervisor.control_plane import BudgetStateError
from supervisor.control_plane import compute_due_jobs
from supervisor.control_plane import consume_from_path
from supervisor.control_plane import dispatch_task
from supervisor.control_plane import load_scheduler_config
from supervisor.control_plane import load_scheduler_state
from supervisor.control_plane import materialize_autonomy_tasks
from supervisor.plugin_loader import DEFAULT_POLICY_PATH as PLUGIN_POLICY_PATH
from supervisor.plugin_loader import DEFAULT_REGISTRY_PATH as PLUGIN_REGISTRY_PATH
from supervisor.plugin_loader import DEFAULT_SCHEMA_PATH as PLUGIN_SCHEMA_PATH
from supervisor.plugin_loader import PluginLoaderError
from supervisor.plugin_loader import discover_plugins
from supervisor.plugin_loader import load_registry
from supervisor.plugin_loader import set_plugin_enabled
from supervisor.budgets import DEFAULT_BUDGETS_PATH
from supervisor.budgets import default_budget_state
from supervisor.budgets import save_budget_state
from supervisor.scheduler import DENY_SCHEDULER_TIME_INVALID
from supervisor.scheduler import SchedulerError
from supervisor.scheduler import parse_utc_iso8601
from supervisor.scheduler.state import DEFAULT_SCHEDULER_STATE_PATH
from supervisor.scheduler.state import write_scheduler_state
from supervisor.state_integrity import StateIntegrityError
from supervisor.state_integrity import update_state_integrity_reference
from supervisor.state_integrity import verify_state_integrity
from supervisor.phase_acceptance import PhaseAcceptanceError
from supervisor.phase_acceptance import load_phase_acceptance_evidence
from supervisor.phase_acceptance import verify_phase_acceptance_evidence
from supervisor.determinism_evidence import DeterminismEvidenceError
from supervisor.determinism_evidence import load_determinism_evidence
from supervisor.determinism_evidence import verify_determinism_evidence
from supervisor.paths import resolve_host_state_dir
from supervisor.agent_workspace import AgentWorkspaceError
from supervisor.agent_workspace import create_workspace_branch
from supervisor.agent_workspace import push_workspace_pr
from supervisor.agent_workspace import run_workspace_tests
from supervisor.agent_workspace import sync_workspace
from supervisor.channels.email_gateway import EmailGatewayError
from supervisor.channels.email_gateway import poll_email_direct
from supervisor.channels.email_gateway import send_email_direct


DRYRUN_QUEUE_YAML = """\
mode: night-autonomy-dryrun-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
"""


def _budget_rejection(results: list[dict]) -> dict | None:
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("status") == "rejected" and "budget" in item:
            return item
    return None


def _print_budget_status(data: dict[str, Any]) -> None:
    print("Budget Status")
    print(f"window_utc_day: {data.get('window_utc_day', '')}")
    print("counts:")
    for key, value in sorted((data.get("counts") or {}).items()):
        print(f"  {key}: {value}")
    print("daily_limits:")
    for key, value in sorted((data.get("daily_limits") or {}).items()):
        print(f"  {key}: {value}")
    print("cooldowns_seconds:")
    for key, value in sorted((data.get("cooldowns_seconds") or {}).items()):
        print(f"  {key}: {value}")


def _print_gate_result(data: dict[str, Any], action_name: str) -> None:
    items = data.get(action_name) or []
    status = str(data.get("status", "ok"))
    print(f"{action_name}: {status}")
    if data.get("reason"):
        print(f"reason: {data['reason']}")
    if "budget" in data:
        budget = data.get("budget") or {}
        print(f"budget.window_utc_day: {budget.get('window_utc_day', '')}")
    print(f"items: {len(items) if isinstance(items, list) else 0}")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                line = f"- status={item.get('status', '')}"
                if item.get("pr_number") is not None:
                    line += f" pr={item.get('pr_number')}"
                if item.get("reason"):
                    line += f" reason={item.get('reason')}"
                print(line)


def _print_materialize_result(data: dict[str, Any]) -> None:
    _print_gate_result(data, "materialized")
    items = data.get("materialized") or []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("task_path"):
                print(f"  task_path={item['task_path']}")


def _print_plugin_result(data: dict[str, Any]) -> None:
    plugins = data.get("plugins") or []
    print(f"plugins: {len(plugins) if isinstance(plugins, list) else 0}")
    if not isinstance(plugins, list):
        return
    for plugin in plugins:
        if not isinstance(plugin, dict):
            continue
        print(
            f"- id={plugin.get('plugin_id','')} enabled={plugin.get('enabled',False)} "
            f"source={plugin.get('source','')} reason={plugin.get('reason_code','')}"
        )


def _print_capability_revoke_request_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    print(f"request_path: {data.get('request_path', '')}")


def _print_capability_revoke_apply_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    print(f"capability: {data.get('capability', '')}")
    print(f"revoke_id: {data.get('revoke_id', '')}")
    print(f"ledger_path: {data.get('ledger_path', '')}")


def _print_capability_activate_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    print(f"capability: {data.get('capability', '')}")
    print(f"state: {data.get('state', '')}")
    print(f"granted: {data.get('granted', False)}")
    print(f"activated_by: {data.get('activated_by', '')}")
    print(f"ledger_path: {data.get('ledger_path', '')}")
    print(f"audit_path: {data.get('audit_path', '')}")


def _print_scheduler_tick_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    if data.get("reason_code"):
        print(f"reason_code: {data.get('reason_code', '')}")
    if data.get("reason"):
        print(f"reason: {data.get('reason', '')}")
    print(f"dry_run: {data.get('dry_run', False)}")
    print(f"jobs_due: {len(data.get('due_events') or [])}")


def _print_agent_workspace_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    if data.get("reason_code"):
        print(f"reason_code: {data.get('reason_code', '')}")
    if data.get("reason"):
        print(f"reason: {data.get('reason', '')}")
    if data.get("agent"):
        print(f"agent: {data.get('agent', '')}")
    if data.get("workspace_repo"):
        print(f"workspace_repo: {data.get('workspace_repo', '')}")
    if data.get("runtime_env_file"):
        print(f"runtime_env_file: {data.get('runtime_env_file', '')}")
    if data.get("mailbox_fixtures_dir"):
        print(f"mailbox_fixtures_dir: {data.get('mailbox_fixtures_dir', '')}")
    if data.get("branch"):
        print(f"branch: {data.get('branch', '')}")
    if data.get("pr_number") is not None:
        print(f"pr_number: {data.get('pr_number')}")
    if data.get("pr_url"):
        print(f"pr_url: {data.get('pr_url', '')}")
    if data.get("exit_code") is not None:
        print(f"exit_code: {data.get('exit_code')}")
    if data.get("command"):
        print(f"command: {data.get('command', '')}")
    if data.get("stdout_tail"):
        print("stdout_tail:")
        print(str(data.get("stdout_tail", "")))
    if data.get("stderr_tail"):
        print("stderr_tail:")
        print(str(data.get("stderr_tail", "")))


def _print_email_gateway_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    if data.get("reason_code"):
        print(f"reason_code: {data.get('reason_code', '')}")
    if data.get("reason"):
        print(f"reason: {data.get('reason', '')}")
    if data.get("agent"):
        print(f"agent: {data.get('agent', '')}")
    if data.get("artifact_path"):
        print(f"artifact_path: {data.get('artifact_path', '')}")
    if data.get("messages") is not None:
        print(f"messages: {data.get('messages', 0)}")
    if data.get("audit_path"):
        print(f"audit_path: {data.get('audit_path', '')}")


def _print_night_run_result(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status', '')}")
    if str(data.get("status", "")) == "rejected":
        if data.get("reject_reason"):
            print(f"reject_reason: {data.get('reject_reason', '')}")
        if data.get("subsystem"):
            print(f"subsystem: {data.get('subsystem', '')}")
        if data.get("detail"):
            print(f"detail: {data.get('detail', '')}")
        if data.get("reason_code"):
            print(f"reason_code: {data.get('reason_code', '')}")
        if data.get("reason"):
            print(f"reason: {data.get('reason', '')}")
        return
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    print(f"tasks_executed: {summary.get('tasks_executed', 0)}")
    print(f"tasks_skipped: {summary.get('tasks_skipped', 0)}")
    print(f"tasks_failed: {summary.get('tasks_failed', 0)}")
    print(f"budget_used: {summary.get('budget_used', 0)}")
    print(f"violations: {','.join(summary.get('violations', [])) if isinstance(summary.get('violations'), list) else ''}")
    print(f"summary_path: {data.get('summary_path', '')}")


def _night_debug_enabled() -> bool:
    return os.environ.get("NIGHT_DEBUG", "").strip() == "1"


def _night_debug_emit(payload: dict[str, Any]) -> None:
    if not _night_debug_enabled():
        return
    print("NIGHT_DEBUG " + json.dumps(payload, sort_keys=True, ensure_ascii=True), file=sys.stderr)


def _night_rejected_payload(
    *,
    reason_code: str,
    reject_reason: str,
    subsystem: str,
    detail: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": "rejected",
        "reason_code": reason_code,
        "reason": reason,
        "reject_reason": reject_reason,
        "subsystem": subsystem,
        "detail": detail,
    }


def _emit_scheduler_event(event: dict[str, Any]) -> dict[str, Any]:
    safe_type = str(event.get("type", "scheduler.job_due"))
    safe_job_id = str(event.get("job_id", "unknown"))
    safe_fired_at = str(event.get("fired_at", ""))
    safe_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    bus_payload = {
        "job_id": safe_job_id,
        "payload": safe_payload,
        "fired_at": safe_fired_at,
    }

    try:
        from kernel.events import emit as emit_event
    except Exception:
        ts_slug = (
            safe_fired_at.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z")
            if safe_fired_at
            else "unknown"
        )
        day = safe_fired_at[:10] if len(safe_fired_at) >= 10 else "unknown-date"
        out_path = (
            Path("logs")
            / "control"
            / "events"
            / day
            / f"{safe_type}__{safe_job_id}__{ts_slug}.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "type": safe_type,
            "job_id": safe_job_id,
            "payload": safe_payload,
            "fired_at": safe_fired_at,
        }
        out_path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        return {"transport": "append_only_file", "path": str(out_path), "ok": True}

    result = emit_event(safe_type, bus_payload)
    return {"transport": "kernel.events", "result": result, "ok": bool(result.get("ok", False))}


def _write_scheduler_run_artifact(record: dict[str, Any]) -> str:
    fired_at = str(record.get("fired_at", ""))
    day = fired_at[:10] if len(fired_at) >= 10 else "unknown-date"
    ts_slug = fired_at.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z") if fired_at else "unknown"
    job_id = str(record.get("job_id", "unknown"))
    out_path = Path("logs") / "control" / "scheduler_runs" / day / f"{job_id}__{ts_slug}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return str(out_path)


def _interrupt_flag_set(state_path: Path) -> bool:
    if not state_path.exists():
        return False
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid interrupt state json: {state_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("interrupt state must be object")
    flag = payload.get("INTERRUPT_FLAG", False)
    if not isinstance(flag, bool):
        raise RuntimeError("INTERRUPT_FLAG must be boolean")
    return flag


def _ensure_autonomy_state_file(state_path: Path) -> None:
    if state_path.exists():
        return
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"INTERRUPT_FLAG": False}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _ensure_budget_state_file(state_path: Path) -> None:
    if state_path.exists():
        return
    save_budget_state(state_path, default_budget_state())


def _write_interrupt_artifact(*, checkpoint: str, now_utc: datetime) -> str:
    day = now_utc.strftime("%Y-%m-%d")
    ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = Path("logs") / "control" / "interrupts" / day / f"interrupt__{checkpoint}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "event": "interrupt_requested",
                "checkpoint": checkpoint,
                "ts_utc": ts,
            },
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(out_path)


def _cmd_autonomy_promote(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        results = create_draft_proposals_prs(
            proposals_dir=args.proposals_dir,
            repo_owner=args.repo_owner,
            repo_name=args.repo_name,
            base_branch=args.base_branch,
        )
    except AutonomyPromotionGateError as exc:
        reason = str(exc)
        if reason == "missing_gitea_token":
            return (
                2,
                {
                    "status": "error",
                    "reason": reason,
                    "expected_env_key": "GITEA_TOKEN",
                    "token_present": bool(str(os.environ.get("GITEA_TOKEN", "")).strip()),
                },
                "gate:promotion",
            )
        raise
    rejected = _budget_rejection(results)
    if rejected is not None:
        return (
            2,
            {
                "status": "rejected",
                "reason": rejected.get("reason"),
                "budget": rejected.get("budget"),
                "promotion": results,
            },
            "gate:promotion",
        )
    return 0, {"promotion": results}, "gate:promotion"


def _cmd_autonomy_intake(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    results = intake_approved_autonomy_proposals(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        base_branch=args.base_branch,
    )
    rejected = _budget_rejection(results)
    if rejected is not None:
        return (
            2,
            {
                "status": "rejected",
                "reason": rejected.get("reason"),
                "budget": rejected.get("budget"),
                "intake": results,
            },
            "gate:intake",
        )
    return 0, {"intake": results}, "gate:intake"


def _cmd_autonomy_materialize(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    results = materialize_autonomy_tasks(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        base_branch=args.base_branch,
        intake_label=args.intake_label,
        host_state_dir=args.host_state_dir,
    )
    rejected = _budget_rejection(results)
    if rejected is not None:
        return (
            2,
            {
                "status": "rejected",
                "reason": rejected.get("reason"),
                "budget": rejected.get("budget"),
                "materialized": results,
            },
            "materialize",
        )
    return 0, {"materialized": results}, "materialize"


def _cmd_autonomy_dryrun(_args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    queue_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    queue_path = Path(queue_file.name)
    queue_file.write(DRYRUN_QUEUE_YAML)
    queue_file.flush()
    queue_file.close()

    had_proposals_dir = Path("docs/autonomy/proposals").is_dir()
    try:
        exit_code, report, report_path = run_night_executor(
            queue_path=str(queue_path),
            ledger_dir=os.environ.get("LEDGER_DIR", "").strip() or None,
        )
        return (
            exit_code,
            {"overall_status": report.get("overall_status"), "report_path": str(report_path)},
            "dryrun",
        )
    finally:
        queue_path.unlink(missing_ok=True)
        proposals_dir = Path("docs/autonomy/proposals")
        if not had_proposals_dir and proposals_dir.is_dir():
            for entry in sorted(proposals_dir.glob("*"), reverse=True):
                if entry.is_file():
                    entry.unlink(missing_ok=True)
            proposals_dir.rmdir()
            proposals_parent = proposals_dir.parent
            if proposals_parent.is_dir() and not any(proposals_parent.iterdir()):
                proposals_parent.rmdir()
            docs_dir = Path("docs")
            if docs_dir.is_dir() and not any(docs_dir.iterdir()):
                docs_dir.rmdir()


def _cmd_autonomy_request_revoke(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    payload = create_revoke_request(repo_root=Path.cwd(), capability=args.capability, justification=args.why)
    return 0, payload, "capability_revoke_request"


def _cmd_autonomy_apply_revoke(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    payload = apply_revoke_request(
        repo_root=Path.cwd(),
        request_path=Path(args.request),
        approval_path=Path(args.approval),
    )
    return 0, payload, "capability_revoke_apply"


def _cmd_autonomy_capability_activate(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = activate_capability(repo_root=Path.cwd(), capability=args.capability, expected_approver="Don")
        return 0, payload, "capability_activate"
    except CapabilityActivationError as exc:
        return (
            2,
            {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)},
            "capability_activate",
        )


def _cmd_autonomy_scheduler_tick(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        if args.now:
            now_utc = parse_utc_iso8601(args.now, DENY_SCHEDULER_TIME_INVALID)
        else:
            now_utc = datetime.now(UTC).replace(microsecond=0)

        interrupt_state_path = Path(
            (os.environ.get("SUPERVISOR_AUTONOMY_STATE_PATH", "") or "").strip() or "state/autonomy_state.json"
        )
        integrity_metadata_path = Path(
            (os.environ.get("SUPERVISOR_INTEGRITY_METADATA_PATH", "") or "").strip()
            or "state/supervisor/state_integrity.json"
        )
        integrity_audit_path = Path(
            (os.environ.get("SUPERVISOR_INTEGRITY_AUDIT_PATH", "") or "").strip()
            or "logs/control/integrity_events.jsonl"
        )
        budget_state_path = Path(args.budget_state_path)
        _ensure_autonomy_state_file(interrupt_state_path)
        _ensure_budget_state_file(budget_state_path)
        verify_state_integrity(
            targets={
                "autonomy_state": interrupt_state_path,
                "budget_state": budget_state_path,
            },
            metadata_path=integrity_metadata_path,
            audit_path=integrity_audit_path,
            now_utc=now_utc,
        )
        if _interrupt_flag_set(interrupt_state_path):
            artifact_path = _write_interrupt_artifact(checkpoint="scheduler_tick", now_utc=now_utc)
            update_state_integrity_reference(
                targets={
                    "autonomy_state": interrupt_state_path,
                    "budget_state": budget_state_path,
                },
                metadata_path=integrity_metadata_path,
                audit_path=integrity_audit_path,
                now_utc=now_utc,
            )
            return (
                2,
                {
                    "status": "halted",
                    "reason_code": "DENY_INTERRUPT_REQUESTED",
                    "reason": "interrupt requested at scheduler tick",
                    "artifact_path": artifact_path,
                },
                "scheduler_tick",
            )

        config = load_scheduler_config(path=Path(args.jobs_path))
        state = load_scheduler_state(path=Path(args.state_path))
        due_events, next_state = compute_due_jobs(config=config, state=state, now_utc=now_utc)

        emit_results: list[dict[str, Any]] = []
        guarded_runs: list[dict[str, Any]] = []
        if not args.dry_run:
            for event in due_events:
                envelope = {
                    "type": str(event.get("type", "scheduler.job_due")),
                    "job_id": str(event.get("job_id", "")),
                    "payload": event.get("payload") if isinstance(event.get("payload"), dict) else {},
                    "fired_at": str(event.get("fired_at", "")),
                }
                emit_results.append(_emit_scheduler_event(envelope))
                if str(event.get("mode", "event_only")) != "guarded_skill":
                    continue

                capability_verdict = check_capability(
                    REQUIRED_SCHEDULER_GUARDED_SKILL_RUN,
                    now_utc=now_utc,
                    ledger_path=Path(args.capability_ledger_path),
                    denylist_path=Path(args.capability_denylist_path),
                )
                task = ""
                payload_obj = event.get("payload")
                if isinstance(payload_obj, dict):
                    task = str(payload_obj.get("task", ""))
                base_record: dict[str, Any] = {
                    "job_id": str(event.get("job_id", "")),
                    "task": task,
                    "fired_at": str(event.get("fired_at", "")),
                }

                if not capability_verdict.get("allow", False):
                    base_record["outcome"] = "deny"
                    base_record["reason_code"] = str(capability_verdict.get("reason_code", "DENY_CAPABILITY_MISSING"))
                    artifact_path = _write_scheduler_run_artifact(base_record)
                    guarded_runs.append({**base_record, "artifact_path": artifact_path})
                    continue

                try:
                    if _interrupt_flag_set(interrupt_state_path):
                        base_record["outcome"] = "deny"
                        base_record["reason_code"] = "DENY_INTERRUPT_REQUESTED"
                        base_record["artifact_path"] = _write_interrupt_artifact(
                            checkpoint="before_budget_consume",
                            now_utc=now_utc,
                        )
                        artifact_path = _write_scheduler_run_artifact(base_record)
                        guarded_runs.append({**base_record, "artifact_path": artifact_path})
                        continue
                    budget_result = consume_from_path(
                        Path(args.budget_state_path),
                        "scheduler_guarded_skill_run",
                        now_utc,
                        cost=1,
                    )
                except BudgetStateError as exc:
                    base_record["outcome"] = "deny"
                    base_record["reason_code"] = exc.reason_code
                    base_record["error"] = str(exc)
                    artifact_path = _write_scheduler_run_artifact(base_record)
                    guarded_runs.append({**base_record, "artifact_path": artifact_path})
                    continue

                if not budget_result.get("ok", False):
                    base_record["outcome"] = "deny"
                    base_record["reason_code"] = str(budget_result.get("reason_code", "DENY_BUDGET_EXCEEDED"))
                    snapshot = budget_result.get("snapshot") if isinstance(budget_result.get("snapshot"), dict) else {}
                    base_record["budget_key"] = snapshot.get("budget_key")
                    base_record["limit"] = snapshot.get("limit")
                    base_record["used"] = snapshot.get("used")
                    base_record["window_start_utc"] = snapshot.get("window_start_utc")
                    artifact_path = _write_scheduler_run_artifact(base_record)
                    guarded_runs.append({**base_record, "artifact_path": artifact_path})
                    continue

                try:
                    handler_result = dispatch_task(task, payload_obj if isinstance(payload_obj, dict) else {}, now_utc=now_utc)
                    base_record["outcome"] = "ok"
                    base_record["handler_result"] = handler_result
                except Exception as exc:
                    base_record["outcome"] = "deny"
                    error_code = getattr(exc, "reason_code", "DENY_SCHEDULER_TASK_FAILED")
                    base_record["reason_code"] = str(error_code)
                    base_record["error"] = str(exc)

                artifact_path = _write_scheduler_run_artifact(base_record)
                guarded_runs.append({**base_record, "artifact_path": artifact_path})
            write_scheduler_state(Path(args.state_path), next_state)

        update_state_integrity_reference(
            targets={
                "autonomy_state": interrupt_state_path,
                "budget_state": budget_state_path,
            },
            metadata_path=integrity_metadata_path,
            audit_path=integrity_audit_path,
            now_utc=now_utc,
        )

        return (
            0,
            {
                "status": "ok",
                "dry_run": bool(args.dry_run),
                "due_events": due_events,
                "emit_results": emit_results,
                "guarded_runs": guarded_runs,
                "state_path": str(Path(args.state_path)),
                "jobs_path": str(Path(args.jobs_path)),
            },
            "scheduler_tick",
        )
    except StateIntegrityError as exc:
        return (
            2,
            {
                "status": "rejected",
                "reason_code": exc.reason_code,
                "reason": str(exc),
            },
            "scheduler_tick",
        )
    except SchedulerError as exc:
        return (
            2,
            {
                "status": "rejected",
                "reason_code": exc.reason_code,
                "reason": str(exc),
            },
            "scheduler_tick",
        )


def _cmd_autonomy_budget_status(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    state, _ = load_or_init_budget_state(host_state_dir=args.host_state_dir)
    return 0, state, "budget_status"


def _cmd_autonomy_budget_reset(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    if not args.force:
        raise RuntimeError("budget reset requires --force")
    try:
        require_approval_token(
            scope="budget_override",
            operation="autonomy_budget_reset",
            token=(os.environ.get("SUPERVISOR_BUDGET_OVERRIDE_TOKEN", "") or "").strip(),
        )
    except ApprovalTokenError as exc:
        return (
            2,
            {
                "status": "rejected",
                "reason_code": exc.reason_code,
                "reason": str(exc),
            },
            "budget_reset",
        )

    state, state_path = load_or_init_budget_state(host_state_dir=args.host_state_dir)
    state, _ = roll_window_if_needed(state)
    state["counts"] = {k: 0 for k in sorted(state.get("counts", {}).keys())}
    state["last_action_epoch_s"] = {k: 0 for k in sorted(state.get("last_action_epoch_s", {}).keys())}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    append_budget_event_log(
        {
            "event": "budget_reset",
            "window_utc_day": state["window_utc_day"],
            "reason": "operator_force_reset",
        },
        host_state_dir=args.host_state_dir,
    )
    return 0, {"status": "ok", "window_utc_day": state["window_utc_day"]}, "budget_reset"


def _cmd_autonomy_improvement_budget_status(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    result = check_budget(
        "improvement",
        context_id="",
        host_state_dir=args.host_state_dir,
    )
    if not result.get("allowed", False):
        return 2, {"status": "rejected", "reason": result.get("reason"), "budget": result.get("state", {})}, "improvement_budget"
    return 0, {"status": "ok", "reason": result.get("reason"), "budget": result.get("state", {})}, "improvement_budget"


def _cmd_autonomy_improvement_budget_consume(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    result = consume_improvement_budget(
        pr_id=args.pr_id,
        tier=args.tier,
        host_state_dir=args.host_state_dir,
    )
    if not result.get("consumed", False):
        return 2, {"status": "rejected", "reason": result.get("reason"), "budget": result.get("state", {}), "pr_id": result.get("pr_id"), "tier": result.get("tier")}, "improvement_budget"
    return 0, {"status": "ok", "reason": result.get("reason"), "budget": result.get("state", {}), "pr_id": result.get("pr_id"), "tier": result.get("tier")}, "improvement_budget"


def _cmd_night_run(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    source = str(getattr(args, "source", "gitea")).strip().lower()
    gitea_base_url = str(os.environ.get("GITEA_BASE_URL", "")).strip()
    gitea_token = str(os.environ.get("GITEA_TOKEN", "")).strip()
    gitea_repo = str(os.environ.get("GITEA_REPO", "")).strip()
    night_agent_id = str(os.environ.get("NIGHT_AGENT_ID", "")).strip() or "night-mode"

    policy_path = resolve_policy_path(Path.cwd(), Path(args.policy_path))
    budget_engine_state_path = Path(args.budget_engine_state_path)
    budget_state_path = Path(args.budget_state_path)
    capability_ledger_path = Path(args.capability_ledger_path)
    capability_denylist_path = Path(args.capability_denylist_path)
    ledger_root = Path(args.ledger_root) if args.ledger_root else None
    specs_dir = Path(args.specs_dir)
    summary_dir = Path(args.summary_dir)
    remote_config_path = Path(args.remote_config_path)
    epoch_id = str(args.epoch).strip() if args.epoch else datetime.now(UTC).strftime("%Y-%m-%d")

    _night_debug_emit({"subsystem": "night_run.preflight", "detail": "resolved_epoch", "epoch": epoch_id})
    _night_debug_emit({"subsystem": "night_run.preflight", "detail": "capability_ledger_path", "path": str((Path.cwd() / capability_ledger_path).resolve())})
    _night_debug_emit({"subsystem": "night_run.preflight", "detail": "budget_state_path", "path": str((Path.cwd() / budget_state_path).resolve())})
    _night_debug_emit({"subsystem": "night_run.preflight", "detail": "budget_engine_state_path", "path": str((Path.cwd() / budget_engine_state_path).resolve())})

    if source == "gitea":
        missing = [
            name
            for name, value in (
                ("GITEA_BASE_URL", gitea_base_url),
                ("GITEA_TOKEN", gitea_token),
                ("GITEA_REPO", gitea_repo),
                ("NIGHT_AGENT_ID", night_agent_id),
            )
            if not value
        ]
        if missing:
            detail = f"missing_env:{','.join(missing)}"
            _night_debug_emit({
                "subsystem": "night_run.preflight.env",
                "validation": "failed",
                "detail": detail,
                "missing_env": missing,
            })
            return 2, _night_rejected_payload(
                reason_code="DENY_STATE_INVALID",
                reject_reason="preflight_validation_failed",
                subsystem="night_run.preflight.env",
                detail=detail,
                reason=f"DENY_STATE_INVALID: {detail}",
            ), "night_run"
    elif source == "local":
        gitea_base_url = ""
        gitea_token = ""
        gitea_repo = ""
    elif source in {"remote", "both"}:
        gitea_base_url = ""
        gitea_token = ""
        gitea_repo = ""
    else:
        return 2, _night_rejected_payload(
            reason_code="DENY_STATE_INVALID",
            reject_reason="preflight_validation_failed",
            subsystem="night_run.preflight.env",
            detail=f"invalid_source:{source}",
            reason=f"DENY_STATE_INVALID: invalid_source:{source}",
        ), "night_run"

    try:
        policy = BudgetEngine.load_policy(policy_path)
        policy_keys = sorted(str(key) for key in policy.keys()) if isinstance(policy, dict) else []
        _night_debug_emit({
            "subsystem": "night_run.preflight.policy",
            "validation": "ok",
            "detail": "policy_load_result",
            "policy_path": str(policy_path),
            "policy_keys": policy_keys,
        })
    except Exception as exc:
        detail = f"policy_load_failed:{exc}"
        _night_debug_emit({
            "subsystem": "night_run.preflight.policy",
            "validation": "failed",
            "detail": detail,
            "policy_path": str(policy_path),
        })
        return 2, _night_rejected_payload(
            reason_code="DENY_STATE_INVALID",
            reject_reason="preflight_validation_failed",
            subsystem="night_run.preflight.policy",
            detail=detail,
            reason=f"DENY_STATE_INVALID: {detail}",
        ), "night_run"

    try:
        runner = NightModeRunner(
            repo_root=Path.cwd(),
            epoch_id=epoch_id,
            policy_path=policy_path,
            budget_engine_state_path=budget_engine_state_path,
            budget_state_path=budget_state_path,
            capability_ledger_path=capability_ledger_path,
            capability_denylist_path=capability_denylist_path,
            ledger_root=ledger_root,
            specs_dir=specs_dir,
            summary_dir=summary_dir,
            agent_id=night_agent_id,
            gitea_base_url=gitea_base_url,
            gitea_token=gitea_token,
            gitea_repo=gitea_repo,
            source_mode=source,
            remote_config_path=remote_config_path,
        )
        payload = runner.run()
        return (0 if payload.get("status") == "ok" else 2), payload, "night_run"
    except (NightModeError, SchedulerError, BudgetStateError) as exc:
        reason_code = str(getattr(exc, "reason_code", "DENY_STATE_INVALID"))
        detail = str(getattr(exc, "detail", str(exc)))
        subsystem = "night_run.run" if "runner" in locals() else "night_run.init"
        _night_debug_emit({
            "subsystem": subsystem,
            "validation": "failed",
            "reason_code": reason_code,
            "detail": detail,
        })
        return 2, _night_rejected_payload(
            reason_code=reason_code,
            reject_reason="night_run_rejected",
            subsystem=subsystem,
            detail=detail,
            reason=str(exc),
        ), "night_run"


def _cmd_plugin_validate(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = discover_plugins(
            scan_dirs=(args.repo_plugins_dir, args.external_plugins_dir),
            schema_path=args.schema,
            policy_path=args.policy,
            registry_path=Path(args.registry_path),
        )
        denied = [p for p in payload.get("plugins", []) if isinstance(p, dict) and not p.get("valid", False)]
        if denied:
            return 2, payload, "plugins"
        return 0, payload, "plugins"
    except PluginLoaderError as exc:
        return 2, {"status": "rejected", "reason": str(exc), "plugins": []}, "plugins"


def _cmd_plugin_list(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    payload = load_registry(registry_path=Path(args.registry_path))
    return 0, payload, "plugins"


def _cmd_plugin_enable(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    payload = set_plugin_enabled(args.plugin_id, True, registry_path=Path(args.registry_path))
    return 0, payload, "plugins"


def _cmd_plugin_disable(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    payload = set_plugin_enabled(args.plugin_id, False, registry_path=Path(args.registry_path))
    return 0, payload, "plugins"


def _cmd_autonomy_phase_acceptance_verify(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        evidence = load_phase_acceptance_evidence(Path(args.evidence_path))
        verdict = verify_phase_acceptance_evidence(evidence)
        return 0, verdict, "phase_acceptance"
    except PhaseAcceptanceError as exc:
        return (
            2,
            {
                "status": "rejected",
                "reason_code": exc.reason_code,
                "reason": str(exc),
            },
            "phase_acceptance",
        )


def _cmd_autonomy_determinism_evidence_verify(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = load_determinism_evidence(Path(args.path))
        verdict = verify_determinism_evidence(payload)
        return 0, verdict, "determinism_evidence"
    except DeterminismEvidenceError as exc:
        return (
            2,
            {
                "status": "rejected",
                "reason_code": exc.reason_code,
                "reason": str(exc),
            },
            "determinism_evidence",
        )


def _cmd_agent_workspace_sync(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = sync_workspace(
            repo_root=Path.cwd(),
            agent=args.agent,
            workspace_root=args.root,
            base_branch=args.base_branch,
            remote=args.remote,
        )
        return 0, payload, "agent_workspace"
    except AgentWorkspaceError as exc:
        return 2, {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)}, "agent_workspace"


def _cmd_agent_workspace_run_tests(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = run_workspace_tests(agent=args.agent, workspace_root=args.root)
        return (0 if payload.get("status") == "ok" else 2), payload, "agent_workspace"
    except AgentWorkspaceError as exc:
        return 2, {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)}, "agent_workspace"


def _cmd_agent_workspace_create_branch(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = create_workspace_branch(agent=args.agent, branch_name=args.name, workspace_root=args.root)
        return 0, payload, "agent_workspace"
    except AgentWorkspaceError as exc:
        return 2, {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)}, "agent_workspace"


def _cmd_agent_workspace_push_pr(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = push_workspace_pr(
            agent=args.agent,
            title=args.title,
            body=args.body,
            base_branch=args.base_branch,
            workspace_root=args.root,
        )
        return 0, payload, "agent_workspace"
    except AgentWorkspaceError as exc:
        return 2, {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)}, "agent_workspace"


def _cmd_email_send(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = send_email_direct(
            repo_root=Path.cwd(),
            agent=args.agent,
            to=args.to,
            subject=args.subject,
            body=args.body,
            epoch=args.epoch,
        )
        return 0, payload, "email_gateway"
    except EmailGatewayError as exc:
        return 2, {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)}, "email_gateway"


def _cmd_email_poll(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    try:
        payload = poll_email_direct(
            repo_root=Path.cwd(),
            agent=args.agent,
            max_messages=int(args.max),
            epoch=args.epoch,
        )
        return 0, payload, "email_gateway"
    except EmailGatewayError as exc:
        return 2, {"status": "rejected", "reason_code": exc.reason_code, "reason": str(exc)}, "email_gateway"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiosctl", description="AI-OS control CLI")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("console", help="Launch interactive aiosctl console")

    autonomy = subparsers.add_parser("autonomy", help="Autonomy control commands")
    autonomy_sub = autonomy.add_subparsers(dest="autonomy_command", required=True)

    promote = autonomy_sub.add_parser("promote", help="Run autonomy promotion gate")
    promote.add_argument("--proposals-dir", default="docs/autonomy/proposals")
    promote.add_argument("--repo-owner", default="N04D")
    promote.add_argument("--repo-name", default="AI-OS")
    promote.add_argument("--base-branch", default="dev")
    promote.set_defaults(handler=_cmd_autonomy_promote)

    intake = autonomy_sub.add_parser("intake", help="Run autonomy review intake gate")
    intake.add_argument("--repo-owner", default="N04D")
    intake.add_argument("--repo-name", default="AI-OS")
    intake.add_argument("--base-branch", default="dev")
    intake.set_defaults(handler=_cmd_autonomy_intake)

    materialize = autonomy_sub.add_parser("materialize", help="Materialize intake-approved tasks")
    materialize.add_argument("--repo-owner", default="N04D")
    materialize.add_argument("--repo-name", default="AI-OS")
    materialize.add_argument("--base-branch", default="dev")
    materialize.add_argument("--intake-label", default="intake-processed")
    materialize.add_argument(
        "--host-state-dir",
        default=str(resolve_host_state_dir()),
    )
    materialize.set_defaults(handler=_cmd_autonomy_materialize)

    dryrun = autonomy_sub.add_parser("dryrun", help="Run night autonomy dry-run mode")
    dryrun.set_defaults(handler=_cmd_autonomy_dryrun)

    request_revoke = autonomy_sub.add_parser("request-revoke", help="Create governed capability revoke request")
    request_revoke.add_argument("--cap", dest="capability", required=True)
    request_revoke.add_argument("--why", required=True)
    request_revoke.set_defaults(handler=_cmd_autonomy_request_revoke)

    apply_revoke = autonomy_sub.add_parser("apply-revoke", help="Apply approved capability revoke request")
    apply_revoke.add_argument("--request", required=True)
    apply_revoke.add_argument("--approval", required=True)
    apply_revoke.set_defaults(handler=_cmd_autonomy_apply_revoke)

    capability_activate = autonomy_sub.add_parser("capability-activate", help="Activate capability via Model A lifecycle")
    capability_activate.add_argument("capability")
    capability_activate.set_defaults(handler=_cmd_autonomy_capability_activate)

    scheduler = autonomy_sub.add_parser("scheduler", help="Scheduler control commands")
    scheduler_sub = scheduler.add_subparsers(dest="scheduler_command", required=True)

    scheduler_tick = scheduler_sub.add_parser("tick", help="Run one deterministic scheduler tick")
    scheduler_tick.add_argument("--now", default="", help="UTC timestamp override (ISO8601)")
    scheduler_tick.add_argument("--dry-run", action="store_true")
    scheduler_tick.add_argument("--jobs-path", default="state/scheduler_jobs.json")
    scheduler_tick.add_argument("--state-path", default=str(DEFAULT_SCHEDULER_STATE_PATH))
    scheduler_tick.add_argument("--capability-ledger-path", default=str(DEFAULT_CAPABILITY_LEDGER_PATH))
    scheduler_tick.add_argument("--capability-denylist-path", default=str(DEFAULT_CAPABILITY_DENYLIST_PATH))
    scheduler_tick.add_argument("--budget-state-path", default=str(DEFAULT_BUDGETS_PATH))
    scheduler_tick.set_defaults(handler=_cmd_autonomy_scheduler_tick)

    budget = autonomy_sub.add_parser("budget", help="Autonomy budget control")
    budget_sub = budget.add_subparsers(dest="budget_command", required=True)

    budget_status = budget_sub.add_parser("status", help="Show budget state")
    budget_status.add_argument(
        "--host-state-dir",
        default=os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR,
    )
    budget_status.set_defaults(handler=_cmd_autonomy_budget_status)

    budget_reset = budget_sub.add_parser("reset", help="Reset budget state for current UTC window")
    budget_reset.add_argument("--force", action="store_true")
    budget_reset.add_argument(
        "--host-state-dir",
        default=os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR,
    )
    budget_reset.set_defaults(handler=_cmd_autonomy_budget_reset)

    improvement_budget = autonomy_sub.add_parser("improvement-budget", help="Self-improvement budget control")
    improvement_budget_sub = improvement_budget.add_subparsers(dest="improvement_budget_command", required=True)

    improvement_budget_status = improvement_budget_sub.add_parser("status", help="Check improvement budget status")
    improvement_budget_status.add_argument(
        "--host-state-dir",
        default=os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR,
    )
    improvement_budget_status.set_defaults(handler=_cmd_autonomy_improvement_budget_status)

    improvement_budget_consume = improvement_budget_sub.add_parser("consume", help="Consume improvement budget")
    improvement_budget_consume.add_argument("--pr-id", required=True)
    improvement_budget_consume.add_argument("--tier", required=True)
    improvement_budget_consume.add_argument(
        "--host-state-dir",
        default=os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR,
    )
    improvement_budget_consume.set_defaults(handler=_cmd_autonomy_improvement_budget_consume)

    phase_acceptance = autonomy_sub.add_parser("phase-acceptance", help="Phase acceptance contract checks")
    phase_acceptance_sub = phase_acceptance.add_subparsers(dest="phase_acceptance_command", required=True)
    phase_acceptance_verify = phase_acceptance_sub.add_parser("verify", help="Verify phase acceptance evidence")
    phase_acceptance_verify.add_argument("--evidence-path", required=True)
    phase_acceptance_verify.set_defaults(handler=_cmd_autonomy_phase_acceptance_verify)

    determinism_evidence = autonomy_sub.add_parser("determinism-evidence", help="Determinism evidence checks")
    determinism_evidence_sub = determinism_evidence.add_subparsers(dest="determinism_evidence_command", required=True)
    determinism_evidence_verify = determinism_evidence_sub.add_parser("verify", help="Verify determinism evidence json")
    determinism_evidence_verify.add_argument("--path", required=True)
    determinism_evidence_verify.set_defaults(handler=_cmd_autonomy_determinism_evidence_verify)

    agent = subparsers.add_parser("agent", help="Agent workspace commands")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_workspace = agent_sub.add_parser("workspace", help="Manage isolated per-agent workspaces")
    agent_workspace_sub = agent_workspace.add_subparsers(dest="workspace_command", required=True)

    agent_sync = agent_workspace_sub.add_parser("sync", help="Sync workspace clone from canonical repository remote")
    agent_sync.add_argument("--agent", required=True)
    agent_sync.add_argument("--root", default="")
    agent_sync.add_argument("--base-branch", default="dev")
    agent_sync.add_argument("--remote", default="")
    agent_sync.set_defaults(handler=_cmd_agent_workspace_sync)

    agent_run_tests = agent_workspace_sub.add_parser("run-tests", help="Run tests in workspace clone")
    agent_run_tests.add_argument("--agent", required=True)
    agent_run_tests.add_argument("--root", default="")
    agent_run_tests.set_defaults(handler=_cmd_agent_workspace_run_tests)

    agent_create_branch = agent_workspace_sub.add_parser("create-branch", help="Create branch in workspace clone")
    agent_create_branch.add_argument("--agent", required=True)
    agent_create_branch.add_argument("--name", required=True)
    agent_create_branch.add_argument("--root", default="")
    agent_create_branch.set_defaults(handler=_cmd_agent_workspace_create_branch)

    agent_push_pr = agent_workspace_sub.add_parser("push-pr", help="Push workspace branch and create draft PR")
    agent_push_pr.add_argument("--agent", required=True)
    agent_push_pr.add_argument("--title", required=True)
    agent_push_pr.add_argument("--body", required=True)
    agent_push_pr.add_argument("--base-branch", default="dev")
    agent_push_pr.add_argument("--root", default="")
    agent_push_pr.set_defaults(handler=_cmd_agent_workspace_push_pr)

    plugin = subparsers.add_parser("plugin", help="Plugin loader commands")
    plugin_sub = plugin.add_subparsers(dest="plugin_command", required=True)

    plugin_common = {
        "registry_path": str(PLUGIN_REGISTRY_PATH),
        "schema": PLUGIN_SCHEMA_PATH,
        "policy": PLUGIN_POLICY_PATH,
        "repo_plugins_dir": "plugins",
        "external_plugins_dir": "/var/lib/ai-os/plugins",
    }

    plugin_validate = plugin_sub.add_parser("validate", help="Discover and validate plugins")
    plugin_validate.add_argument("--registry-path", default=plugin_common["registry_path"])
    plugin_validate.add_argument("--schema", default=plugin_common["schema"])
    plugin_validate.add_argument("--policy", default=plugin_common["policy"])
    plugin_validate.add_argument("--repo-plugins-dir", default=plugin_common["repo_plugins_dir"])
    plugin_validate.add_argument("--external-plugins-dir", default=plugin_common["external_plugins_dir"])
    plugin_validate.set_defaults(handler=_cmd_plugin_validate)

    plugin_list = plugin_sub.add_parser("list", help="List plugin registry")
    plugin_list.add_argument("--registry-path", default=plugin_common["registry_path"])
    plugin_list.set_defaults(handler=_cmd_plugin_list)

    plugin_enable = plugin_sub.add_parser("enable", help="Enable plugin by id")
    plugin_enable.add_argument("plugin_id")
    plugin_enable.add_argument("--registry-path", default=plugin_common["registry_path"])
    plugin_enable.set_defaults(handler=_cmd_plugin_enable)

    plugin_disable = plugin_sub.add_parser("disable", help="Disable plugin by id")
    plugin_disable.add_argument("plugin_id")
    plugin_disable.add_argument("--registry-path", default=plugin_common["registry_path"])
    plugin_disable.set_defaults(handler=_cmd_plugin_disable)

    email = subparsers.add_parser("email", help="Email gateway direct-dispatch commands")
    email_sub = email.add_subparsers(dest="email_command", required=True)

    email_send = email_sub.add_parser("send", help="Send outbound email via governed gateway")
    email_send.add_argument("--agent", required=True)
    email_send.add_argument("--to", required=True)
    email_send.add_argument("--subject", required=True)
    email_send.add_argument("--body", required=True)
    email_send.add_argument("--epoch", default="")
    email_send.set_defaults(handler=_cmd_email_send)

    email_poll = email_sub.add_parser("poll", help="Poll inbound email via governed gateway")
    email_poll.add_argument("--agent", required=True)
    email_poll.add_argument("--max", required=True, type=int)
    email_poll.add_argument("--epoch", default="")
    email_poll.set_defaults(handler=_cmd_email_poll)

    night_run = subparsers.add_parser("night-run", help="Run deterministic night mode loop")
    night_run.add_argument("--source", default="gitea", choices=["gitea", "local", "remote", "both"], help="Issue source backend")
    night_run.add_argument("--epoch", default="", help="UTC epoch id YYYY-MM-DD")
    night_run.add_argument("--policy-path", default="governance_policy.yaml")
    night_run.add_argument("--budget-engine-state-path", default=str(DEFAULT_BUDGETS_PATH))
    night_run.add_argument("--budget-state-path", default="state/budgets.json")
    night_run.add_argument("--capability-ledger-path", default=str(DEFAULT_CAPABILITY_LEDGER_PATH))
    night_run.add_argument("--capability-denylist-path", default=str(DEFAULT_CAPABILITY_DENYLIST_PATH))
    night_run.add_argument("--ledger-root", default="audit/budget_ledger")
    night_run.add_argument("--specs-dir", default="state/night_specs")
    night_run.add_argument("--summary-dir", default="logs/control/night_runs")
    night_run.add_argument("--remote-config-path", default="config/remote_sources.yaml")
    night_run.set_defaults(handler=_cmd_night_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "console":
            from supervisor import console

            return int(console.main())
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.print_help()
            return 1
        exit_code, payload, kind = handler(args)
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            if kind == "budget_status":
                _print_budget_status(payload)
            elif kind == "gate:promotion":
                _print_gate_result(payload, "promotion")
            elif kind == "gate:intake":
                _print_gate_result(payload, "intake")
            elif kind == "materialize":
                _print_materialize_result(payload)
            elif kind == "dryrun":
                print(f"dryrun: {payload.get('overall_status', '')}")
                print(f"report_path: {payload.get('report_path', '')}")
            elif kind == "budget_reset":
                print(f"budget reset: {payload.get('status', '')}")
                print(f"window_utc_day: {payload.get('window_utc_day', '')}")
            elif kind == "plugins":
                _print_plugin_result(payload)
            elif kind == "capability_revoke_request":
                _print_capability_revoke_request_result(payload)
            elif kind == "capability_revoke_apply":
                _print_capability_revoke_apply_result(payload)
            elif kind == "capability_activate":
                _print_capability_activate_result(payload)
            elif kind == "scheduler_tick":
                _print_scheduler_tick_result(payload)
            elif kind == "agent_workspace":
                _print_agent_workspace_result(payload)
            elif kind == "email_gateway":
                _print_email_gateway_result(payload)
            elif kind == "night_run":
                _print_night_run_result(payload)
            elif kind == "phase_acceptance":
                print(f"status: {payload.get('status', '')}")
                if payload.get("reason_code"):
                    print(f"reason_code: {payload.get('reason_code', '')}")
                if payload.get("reason"):
                    print(f"reason: {payload.get('reason', '')}")
            elif kind == "determinism_evidence":
                print(f"status: {payload.get('status', '')}")
                if payload.get("reason_code"):
                    print(f"reason_code: {payload.get('reason_code', '')}")
                if payload.get("reason"):
                    print(f"reason: {payload.get('reason', '')}")
            elif kind == "improvement_budget":
                print(f"status: {payload.get('status', '')}")
                if payload.get("reason"):
                    print(f"reason: {payload.get('reason', '')}")
                if payload.get("pr_id"):
                    print(f"pr_id: {payload.get('pr_id', '')}")
                if payload.get("tier"):
                    print(f"tier: {payload.get('tier', '')}")
            else:
                print(json.dumps(payload, sort_keys=True))
        return int(exit_code)
    except Exception as exc:
        if "args" in locals() and getattr(args, "json", False):
            print(json.dumps({"status": "error", "reason": str(exc)}, sort_keys=True))
        else:
            print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

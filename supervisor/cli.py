from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from supervisor.autonomy_budget import DEFAULT_HOST_STATE_DIR
from supervisor.autonomy_budget import append_budget_event_log
from supervisor.autonomy_budget import load_or_init_budget_state
from supervisor.autonomy_budget import roll_window_if_needed
from supervisor.autonomy_promotion_gate import create_draft_proposals_prs
from supervisor.autonomy_review_intake_gate import intake_approved_autonomy_proposals
from supervisor.autonomy_task_materializer import materialize_autonomy_tasks
from supervisor.night_executor import run_night_executor
from supervisor.plugin_loader import DEFAULT_POLICY_PATH as PLUGIN_POLICY_PATH
from supervisor.plugin_loader import DEFAULT_REGISTRY_PATH as PLUGIN_REGISTRY_PATH
from supervisor.plugin_loader import DEFAULT_SCHEMA_PATH as PLUGIN_SCHEMA_PATH
from supervisor.plugin_loader import PluginLoaderError
from supervisor.plugin_loader import discover_plugins
from supervisor.plugin_loader import load_registry
from supervisor.plugin_loader import set_plugin_enabled


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


def _cmd_autonomy_promote(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    results = create_draft_proposals_prs(
        proposals_dir=args.proposals_dir,
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


def _cmd_autonomy_budget_status(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    state, _ = load_or_init_budget_state(host_state_dir=args.host_state_dir)
    return 0, state, "budget_status"


def _cmd_autonomy_budget_reset(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    if not args.force:
        raise RuntimeError("budget reset requires --force")

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
        default=os.environ.get("HOST_STATE_DIR", "").strip() or "/home/infra/night/state",
    )
    materialize.set_defaults(handler=_cmd_autonomy_materialize)

    dryrun = autonomy_sub.add_parser("dryrun", help="Run night autonomy dry-run mode")
    dryrun.set_defaults(handler=_cmd_autonomy_dryrun)

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

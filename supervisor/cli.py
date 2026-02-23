from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from supervisor.autonomy_promotion_gate import create_draft_proposals_prs
from supervisor.autonomy_review_intake_gate import intake_approved_autonomy_proposals
from supervisor.autonomy_task_materializer import materialize_autonomy_tasks
from supervisor.night_executor import run_night_executor


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


def _cmd_autonomy_promote(args: argparse.Namespace) -> int:
    results = create_draft_proposals_prs(
        proposals_dir=args.proposals_dir,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        base_branch=args.base_branch,
    )
    print(json.dumps({"promotion": results}, sort_keys=True))
    return 0


def _cmd_autonomy_intake(args: argparse.Namespace) -> int:
    results = intake_approved_autonomy_proposals(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        base_branch=args.base_branch,
    )
    print(json.dumps({"intake": results}, sort_keys=True))
    return 0


def _cmd_autonomy_materialize(args: argparse.Namespace) -> int:
    results = materialize_autonomy_tasks(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        base_branch=args.base_branch,
        intake_label=args.intake_label,
        host_state_dir=args.host_state_dir,
    )
    print(json.dumps({"materialized": results}, sort_keys=True))
    return 0


def _cmd_autonomy_dryrun(_args: argparse.Namespace) -> int:
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
        print(
            json.dumps(
                {
                    "overall_status": report.get("overall_status"),
                    "report_path": str(report_path),
                },
                sort_keys=True,
            )
        )
        return exit_code
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiosctl", description="AI-OS control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

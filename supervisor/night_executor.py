from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from supervisor.ledger import compute_run_id
from supervisor.ledger import ingest_evaluation_record_linked
from supervisor.ledger import mark_run_committed
from supervisor.autonomy_observer import analyze_ledger
from supervisor.autonomy_planner import generate_proposals
from supervisor.budgets.autonomy import DEFAULT_HOST_STATE_DIR
from supervisor.budgets.autonomy import consume_budget
from supervisor.autonomy_promotion_gate import create_draft_proposals_prs
from supervisor.autonomy_review_intake_gate import intake_approved_autonomy_proposals
from supervisor.night_task_runner import execute_night_task
from supervisor.results import ingest_run_record

QUEUE_REQUIRED_KEYS = {
    "mode",
    "max_tasks",
    "max_commits",
    "max_attempts_per_task",
    "stop_on_first_failure",
    "allowed_paths",
    "forbidden_paths",
    "task_sources",
}
TASK_SOURCE_REQUIRED_KEYS = {"issue", "spec"}
SUPPORTED_QUEUE_MODES = {
    "night-v0.1",
    "night-autonomy-dryrun-v0.1",
    "night-autonomy-promote-v0.1",
    "night-autonomy-intake-v0.1",
}

TEST_HARNESS_EXIT_CATEGORY = {
    0: "success",
    20: "git_untrusted",
    21: "git_dirty",
    22: "runner_missing",
    23: "tests_failed",
}


def _check_and_consume_budget(action_type: str, *, subject_id: str, host_state_dir: str) -> dict[str, Any]:
    result = consume_budget(
        action_type,
        context_id="",
        host_state_dir=host_state_dir,
    )
    raw_reason = str(result.get("reason") or "budget_internal_error")
    reason = "daily_limit_exhausted" if raw_reason == "budget_exceeded" else raw_reason
    return {
        "allowed": bool(result.get("consumed", False)),
        "reason": reason,
    }


def check_and_consume(action_type: str, *, subject_id: str, host_state_dir: str) -> dict[str, Any]:
    return _check_and_consume_budget(
        action_type,
        subject_id=subject_id,
        host_state_dir=host_state_dir,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso8601(ts: datetime | None = None) -> str:
    base = ts or _utc_now()
    return base.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _normalize_prefixes(raw: Any, key: str) -> list[str]:
    if not isinstance(raw, list) or any(not isinstance(v, str) or not v for v in raw):
        raise ValueError(f"queue key '{key}' must be a non-empty list of non-empty strings")
    return list(raw)


def load_queue(queue_path: str | os.PathLike[str]) -> dict[str, Any]:
    path = Path(queue_path)
    if not path.is_file():
        raise FileNotFoundError(f"queue file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("queue YAML must be a mapping")

    missing = sorted(QUEUE_REQUIRED_KEYS - set(parsed.keys()))
    if missing:
        raise ValueError(f"queue missing required keys: {', '.join(missing)}")

    mode = parsed.get("mode")
    if not isinstance(mode, str) or not mode:
        raise ValueError("queue key 'mode' must be a non-empty string")
    if mode not in SUPPORTED_QUEUE_MODES:
        raise ValueError(f"unsupported queue mode: {mode}")

    int_keys = ("max_tasks", "max_commits", "max_attempts_per_task")
    for key in int_keys:
        value = parsed.get(key)
        min_value = 1
        if mode in (
            "night-autonomy-dryrun-v0.1",
            "night-autonomy-promote-v0.1",
            "night-autonomy-intake-v0.1",
        ) and key in (
            "max_tasks",
            "max_commits",
        ):
            min_value = 0
        if not isinstance(value, int) or value < min_value:
            raise ValueError(f"queue key '{key}' must be an integer >= {min_value}")

    stop_on_first_failure = parsed.get("stop_on_first_failure")
    if not isinstance(stop_on_first_failure, bool):
        raise ValueError("queue key 'stop_on_first_failure' must be boolean")

    allowed_paths = _normalize_prefixes(parsed.get("allowed_paths"), "allowed_paths")
    forbidden_paths = _normalize_prefixes(parsed.get("forbidden_paths"), "forbidden_paths")

    task_sources = parsed.get("task_sources")
    if not isinstance(task_sources, list):
        raise ValueError("queue key 'task_sources' must be a list")

    normalized_tasks: list[dict[str, Any]] = []
    for idx, task in enumerate(task_sources):
        if not isinstance(task, dict):
            raise ValueError(f"task_sources[{idx}] must be a mapping")
        missing_task = sorted(TASK_SOURCE_REQUIRED_KEYS - set(task.keys()))
        if missing_task:
            raise ValueError(
                f"task_sources[{idx}] missing required keys: {', '.join(missing_task)}"
            )

        issue = task.get("issue")
        if isinstance(issue, int):
            issue_value = str(issue)
        elif isinstance(issue, str) and issue.strip():
            issue_value = issue.strip()
        else:
            raise ValueError(f"task_sources[{idx}].issue must be non-empty str/int")

        spec = task.get("spec")
        if not isinstance(spec, str) or not spec.strip():
            raise ValueError(f"task_sources[{idx}].spec must be a non-empty string")

        normalized_tasks.append({"issue": issue_value, "spec": spec.strip()})

    return {
        "mode": mode,
        "max_tasks": int(parsed["max_tasks"]),
        "max_commits": int(parsed["max_commits"]),
        "max_attempts_per_task": int(parsed["max_attempts_per_task"]),
        "stop_on_first_failure": bool(stop_on_first_failure),
        "allowed_paths": allowed_paths,
        "forbidden_paths": forbidden_paths,
        "task_sources": normalized_tasks,
    }


def _run_checked(cmd: list[str], cwd: str | os.PathLike[str] | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _compute_fallback_env_fingerprint() -> str:
    try:
        git_head = _run_checked(["git", "rev-parse", "HEAD"])
    except Exception:
        git_head = "unknown-head"
    os_uname = "|".join(platform.uname())
    py_ver = platform.python_version()
    payload = f"{git_head}|{os_uname}|{py_ver}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_env_fingerprint() -> str:
    try:
        from supervisor import environment_validation as env_validation
    except Exception:
        return _compute_fallback_env_fingerprint()

    for name in (
        "compute_env_fingerprint",
        "compute_environment_fingerprint",
        "get_environment_fingerprint",
        "environment_fingerprint",
    ):
        fn = getattr(env_validation, name, None)
        if callable(fn):
            try:
                value = fn()
            except Exception:
                continue
            if isinstance(value, str) and value:
                return value
    return _compute_fallback_env_fingerprint()


def _path_allowed(path: str, allowed_prefixes: list[str], forbidden_prefixes: list[str]) -> bool:
    allowed = any(path.startswith(prefix) for prefix in allowed_prefixes)
    forbidden = any(path.startswith(prefix) for prefix in forbidden_prefixes)
    return allowed and not forbidden


def _build_report_path(report_dir: str | os.PathLike[str], report_ts: datetime) -> Path:
    folder = Path(report_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = report_ts.strftime("%Y%m%dT%H%M%SZ")
    return folder / f"night-report.{stamp}.json"


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_preflight() -> dict[str, Any]:
    preflight: dict[str, Any] = {
        "git_clean": False,
        "tests_passed": False,
        "test_harness_exit_code": None,
        "test_harness_exit_category": "unknown",
        "test_harness_stdout": "",
        "test_harness_stderr": "",
    }

    status = _run_checked(["git", "status", "--porcelain"])
    if status:
        raise RuntimeError("preflight_failed:git_worktree_dirty")
    preflight["git_clean"] = True

    harness_env = os.environ.copy()
    harness_env.pop("GITEA_TOKEN", None)
    harness_env.pop("GITEA_BASE_URL", None)

    harness = subprocess.run(
        ["./scripts/test-all.sh"],
        capture_output=True,
        text=True,
        env=harness_env,
    )
    preflight["test_harness_exit_code"] = harness.returncode
    preflight["test_harness_exit_category"] = TEST_HARNESS_EXIT_CATEGORY.get(
        harness.returncode,
        "unknown",
    )
    preflight["test_harness_stdout"] = harness.stdout
    preflight["test_harness_stderr"] = harness.stderr
    preflight["tests_passed"] = harness.returncode == 0
    if harness.returncode != 0:
        raise RuntimeError(
            f"preflight_failed:test_harness_failed:{preflight['test_harness_exit_category']}"
        )
    return preflight


def _resolve_ledger_paths(
    *,
    ledger_dir: str | os.PathLike[str] | None,
    runs_path: str | os.PathLike[str] | None,
    evaluations_path: str | os.PathLike[str] | None,
) -> tuple[str, str]:
    resolved_ledger_dir = str(
        ledger_dir
        or os.environ.get("LEDGER_DIR", "").strip()
        or "ledger"
    )
    Path(resolved_ledger_dir).mkdir(parents=True, exist_ok=True)
    resolved_runs_path = str(runs_path or (Path(resolved_ledger_dir) / "runs.jsonl"))
    resolved_evaluations_path = str(
        evaluations_path or (Path(resolved_ledger_dir) / "evaluations.jsonl")
    )
    return resolved_runs_path, resolved_evaluations_path


def _normalize_execution(execution: dict[str, Any] | None) -> dict[str, Any]:
    if execution is None:
        ts_now = int(_utc_now().timestamp() * 1000)
        return {
            "status": "failure",
            "reason": "null_execution",
            "stdout": "",
            "stderr": "",
            "changed_files": [],
            "tests_passed": False,
            "ts_start_ms": ts_now,
            "ts_end_ms": ts_now,
        }

    status = str(execution.get("status", "failure"))
    if not status:
        status = "failure"
    reason = execution.get("reason")
    normalized_reason = None if status == "success" else (
        str(reason) if reason is not None and str(reason) else "execution_failed"
    )
    ts_start_ms = execution.get("ts_start_ms")
    ts_end_ms = execution.get("ts_end_ms")
    ts_now = int(_utc_now().timestamp() * 1000)
    return {
        "status": status,
        "reason": normalized_reason,
        "stdout": str(execution.get("stdout", "")),
        "stderr": str(execution.get("stderr", "")),
        "changed_files": [x for x in execution.get("changed_files", []) if isinstance(x, str)],
        "tests_passed": bool(execution.get("tests_passed", False)),
        "ts_start_ms": ts_start_ms if isinstance(ts_start_ms, int) else ts_now,
        "ts_end_ms": ts_end_ms if isinstance(ts_end_ms, int) else ts_now,
    }


def run_night_executor(
    *,
    queue_path: str,
    ledger_dir: str | os.PathLike[str] | None = None,
    runs_path: str | os.PathLike[str] | None = None,
    evaluations_path: str | os.PathLike[str] | None = None,
    report_dir: str = "state/night-reports",
    run_preflight: bool = True,
) -> tuple[int, dict[str, Any], Path]:
    start_ts = _utc_now()
    report: dict[str, Any] = {
        "version": "night-executor.v0.1",
        "started_at": _utc_iso8601(start_ts),
        "queue_path": queue_path,
        "overall_status": "failed",
        "preflight": {},
        "env_fingerprint": "",
        "entrypoint": None,
        "summary": {
            "tasks_total": 0,
            "tasks_attempted": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "commits_performed": 0,
            "errors": [],
        },
        "tasks": [],
    }
    report_path = _build_report_path(report_dir, start_ts)
    exit_code = 1

    try:
        resolved_runs_path, resolved_evaluations_path = _resolve_ledger_paths(
            ledger_dir=ledger_dir,
            runs_path=runs_path,
            evaluations_path=evaluations_path,
        )
        report["runs_path"] = resolved_runs_path
        report["evaluations_path"] = resolved_evaluations_path

        queue = load_queue(queue_path)
        report["queue_mode"] = queue["mode"]
        report["summary"]["tasks_total"] = min(
            len(queue["task_sources"]), int(queue["max_tasks"])
        )

        if run_preflight:
            report["preflight"] = _run_preflight()
        else:
            report["preflight"] = {"skipped": True}

        env_fingerprint = compute_env_fingerprint()
        report["env_fingerprint"] = env_fingerprint
        report["entrypoint"] = "supervisor.night_task_runner.execute_night_task"

        commits_done = 0
        should_stop = False
        budget_host_state_dir = os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR
        if queue["mode"] == "night-autonomy-dryrun-v0.1":
            opportunities = analyze_ledger(resolved_runs_path, resolved_evaluations_path)
            proposals = generate_proposals(opportunities, "docs/autonomy/proposals")
            report["autonomy"] = {
                "opportunities": opportunities,
                "proposals_generated": proposals,
            }
            report["summary"]["commits_performed"] = 0
            report["overall_status"] = "dryrun_complete"
            exit_code = 0
            return exit_code, report, report_path
        if queue["mode"] == "night-autonomy-promote-v0.1":
            opportunities = analyze_ledger(resolved_runs_path, resolved_evaluations_path)
            proposals = generate_proposals(
                opportunities,
                "docs/autonomy/proposals",
                write_files=False,
            )
            promotion = create_draft_proposals_prs(proposals=proposals)
            report["autonomy"] = {
                "opportunities": opportunities,
                "proposals_generated": proposals,
                "promotion": promotion,
            }
            report["summary"]["commits_performed"] = 0
            report["overall_status"] = "promote_complete"
            exit_code = 0
            return exit_code, report, report_path
        if queue["mode"] == "night-autonomy-intake-v0.1":
            intake = intake_approved_autonomy_proposals()
            report["autonomy"] = {
                "intake": intake,
            }
            report["summary"]["commits_performed"] = 0
            report["overall_status"] = "intake_complete"
            exit_code = 0
            return exit_code, report, report_path

        for task_source in queue["task_sources"][: queue["max_tasks"]]:
            task_id = f"issue:{task_source['issue']}"
            spec_path = task_source["spec"]
            task_report = {
                "task_id": task_id,
                "issue": task_source["issue"],
                "spec": spec_path,
                "attempts": [],
                "final_status": "failed",
            }
            report["summary"]["tasks_attempted"] += 1

            spec_file = Path(spec_path)
            if not spec_file.is_file():
                task_report["final_status"] = "rejected"
                task_report["failure_reason"] = "missing_spec_file"
                report["tasks"].append(task_report)
                report["summary"]["tasks_failed"] += 1
                if queue["stop_on_first_failure"]:
                    should_stop = True
                if should_stop:
                    break
                continue

            spec_bytes = spec_file.read_bytes()
            task_spec_hash = _sha256_bytes(spec_bytes)
            task_report["task_spec_hash"] = task_spec_hash

            task_succeeded = False
            for attempt_no in range(1, queue["max_attempts_per_task"] + 1):
                run_id = compute_run_id(task_id, task_spec_hash, env_fingerprint, attempt_no)
                attempt_budget = check_and_consume(
                    "exec_attempt",
                    subject_id=f"{task_id}#{attempt_no}",
                    host_state_dir=budget_host_state_dir,
                )
                if not attempt_budget.get("allowed", False):
                    ts_now = int(_utc_now().timestamp() * 1000)
                    execution = _normalize_execution(
                        {
                            "status": "failure",
                            "reason": f"budget_blocked:{attempt_budget.get('reason')}",
                            "stdout": "",
                            "stderr": "",
                            "changed_files": [],
                            "tests_passed": False,
                            "ts_start_ms": ts_now,
                            "ts_end_ms": ts_now,
                        }
                    )
                else:
                    execution = _normalize_execution(
                        execute_night_task(
                            int(task_source["issue"]),
                            spec_path,
                        )
                    )

                run_record = {
                    "version": "v0.1",
                    "run_id": run_id,
                    "task_id": task_id,
                    "attempt_no": attempt_no,
                    "env_fingerprint": env_fingerprint,
                    "task_spec_hash": task_spec_hash,
                    "status": execution["status"],
                    "stdout": execution["stdout"],
                    "stderr": execution["stderr"],
                    "ts_start_ms": execution["ts_start_ms"],
                    "ts_end_ms": execution["ts_end_ms"],
                }
                run_ingest = ingest_run_record(resolved_runs_path, run_record)

                changed_files = [f for f in execution["changed_files"] if isinstance(f, str)]
                commit_eligible = bool(changed_files) and bool(execution["tests_passed"]) and all(
                    _path_allowed(f, queue["allowed_paths"], queue["forbidden_paths"])
                    for f in changed_files
                )
                can_commit = (
                    execution["status"] == "success"
                    and commit_eligible
                    and commits_done < queue["max_commits"]
                )

                commit_budget_reason = None
                if can_commit:
                    commit_budget = check_and_consume(
                        "commit",
                        subject_id=task_id,
                        host_state_dir=budget_host_state_dir,
                    )
                    if not commit_budget.get("allowed", False):
                        can_commit = False
                        commit_budget_reason = str(commit_budget.get("reason"))

                if can_commit:
                    try:
                        from orchestrator.git import create_governed_commit

                        commit_result = create_governed_commit(
                            SimpleNamespace(changed_files=changed_files),
                            {"allowed_files": changed_files, "task_id": task_source["issue"]},
                        )
                    except Exception:
                        commit_result = {
                            "commit_created": False,
                            "commit_hash": None,
                            "files_committed": [],
                        }
                else:
                    commit_result = {
                        "commit_created": False,
                        "commit_hash": None,
                        "files_committed": [],
                    }

                if commit_result["commit_created"]:
                    commits_done += 1
                    eval_record = {
                        "run_id": run_id,
                        "task_id": task_id,
                        "evaluation_result": "success",
                        "timestamp": _utc_iso8601(),
                        "commit_sha": commit_result["commit_hash"],
                    }
                    eval_ingest = mark_run_committed(resolved_evaluations_path, eval_record)
                else:
                    eval_record = {
                        "run_id": run_id,
                        "task_id": task_id,
                        "evaluation_result": "success"
                        if execution["status"] == "success"
                        else "rejected",
                        "timestamp": _utc_iso8601(),
                    }
                    if execution["status"] != "success":
                        eval_record["rejection_reason"] = execution["reason"]
                    eval_ingest = ingest_evaluation_record_linked(
                        resolved_evaluations_path, resolved_runs_path, eval_record
                    )

                attempt_report = {
                    "attempt_no": attempt_no,
                    "run_id": run_id,
                    "run_status": execution["status"],
                    "run_reason": execution["reason"],
                    "run_ingest_status": run_ingest.get("status"),
                    "evaluation_ingest_status": eval_ingest.get("status"),
                    "evaluation_result": eval_record["evaluation_result"],
                    "commit_eligible": commit_eligible,
                    "commit_created": bool(commit_result["commit_created"]),
                    "commit_sha": commit_result["commit_hash"],
                    "budget_commit_reason": commit_budget_reason,
                }
                task_report["attempts"].append(attempt_report)

                if execution["status"] == "success":
                    task_succeeded = True
                    task_report["final_status"] = "success"
                    break

            if task_succeeded:
                report["summary"]["tasks_succeeded"] += 1
            else:
                report["summary"]["tasks_failed"] += 1
                task_report["final_status"] = "rejected"
                if queue["stop_on_first_failure"]:
                    should_stop = True

            report["tasks"].append(task_report)
            if should_stop:
                break

        report["summary"]["commits_performed"] = commits_done
        if report["summary"]["tasks_failed"] == 0:
            report["overall_status"] = "success"
            exit_code = 0
        else:
            report["overall_status"] = "failed"
            exit_code = 1
    except Exception as exc:
        report["summary"]["errors"].append(str(exc))
        report["overall_status"] = "failed"
        exit_code = 1
    finally:
        report["finished_at"] = _utc_iso8601()
        _write_report(report_path, report)

    return exit_code, report, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Night Executor v0.1 fail-closed runner")
    parser.add_argument(
        "--queue",
        required=True,
        help="Path to governance night queue YAML (example: governance/night-queue.yaml)",
    )
    parser.add_argument(
        "--ledger-dir",
        default=os.environ.get("LEDGER_DIR", "").strip() or None,
        help="Directory for runs/evaluations ledgers (default: $LEDGER_DIR or ./ledger)",
    )
    args = parser.parse_args(argv)

    exit_code, report, report_path = run_night_executor(
        queue_path=args.queue,
        ledger_dir=args.ledger_dir,
    )
    print(json.dumps({"report_path": str(report_path), "overall_status": report["overall_status"]}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

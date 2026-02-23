from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from supervisor.night_executor import load_queue
from supervisor.night_executor import _run_preflight
from supervisor.night_executor import run_night_executor


def _valid_queue_yaml() -> str:
    return """\
mode: night-v0.1
max_tasks: 2
max_commits: 1
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources:
  - issue: 99
    spec: docs/missing-spec.md
"""


class NightExecutorTests(unittest.TestCase):
    def test_preflight_scrubs_gitea_secrets_from_harness_env(self) -> None:
        captured_env: dict[str, str] = {}

        def fake_subprocess_run(*_args, **kwargs):  # type: ignore[no-untyped-def]
            env = kwargs.get("env")
            if isinstance(env, dict):
                captured_env.update(env)
            return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

        with (
            patch.dict(
                os.environ,
                {"GITEA_TOKEN": "secret-token", "GITEA_BASE_URL": "http://secret-base"},
                clear=False,
            ),
            patch("supervisor.night_executor._run_checked", return_value=""),
            patch("supervisor.night_executor.subprocess.run", side_effect=fake_subprocess_run),
        ):
            result = _run_preflight()

        self.assertTrue(result["tests_passed"])
        self.assertNotIn("GITEA_TOKEN", captured_env)
        self.assertNotIn("GITEA_BASE_URL", captured_env)

    def test_queue_schema_validation_rejects_missing_required_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue_path = Path(tmp_dir) / "night-queue.yaml"
            queue_path.write_text("mode: night-v0.1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_queue(queue_path)

    def test_dryrun_queue_allows_zero_task_and_commit_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue_path = Path(tmp_dir) / "night-queue.yaml"
            queue_path.write_text(
                """\
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
""",
                encoding="utf-8",
            )
            queue = load_queue(queue_path)
            self.assertEqual(queue["max_tasks"], 0)
            self.assertEqual(queue["max_commits"], 0)

    def test_promote_queue_allows_zero_task_and_commit_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue_path = Path(tmp_dir) / "night-queue.yaml"
            queue_path.write_text(
                """\
mode: night-autonomy-promote-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
""",
                encoding="utf-8",
            )
            queue = load_queue(queue_path)
            self.assertEqual(queue["max_tasks"], 0)
            self.assertEqual(queue["max_commits"], 0)

    def test_intake_queue_allows_zero_task_and_commit_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue_path = Path(tmp_dir) / "night-queue.yaml"
            queue_path.write_text(
                """\
mode: night-autonomy-intake-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
""",
                encoding="utf-8",
            )
            queue = load_queue(queue_path)
            self.assertEqual(queue["max_tasks"], 0)
            self.assertEqual(queue["max_commits"], 0)

    def test_report_generation_includes_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            queue_path = tmp_root / "night-queue.yaml"
            queue_path.write_text(_valid_queue_yaml(), encoding="utf-8")
            report_dir = tmp_root / "reports"

            exit_code, report, report_path = run_night_executor(
                queue_path=str(queue_path),
                runs_path=str(tmp_root / "runs.jsonl"),
                evaluations_path=str(tmp_root / "evaluations.jsonl"),
                report_dir=str(report_dir),
                run_preflight=False,
            )

            self.assertEqual(exit_code, 1)
            self.assertTrue(report_path.is_file())
            self.assertEqual(report["version"], "night-executor.v0.1")
            self.assertIn("started_at", report)
            self.assertIn("finished_at", report)
            self.assertIn("summary", report)
            self.assertIn("tasks", report)
            self.assertIn("overall_status", report)

    def test_fail_closed_when_queue_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            missing_queue = tmp_root / "does-not-exist.yaml"

            exit_code, report, report_path = run_night_executor(
                queue_path=str(missing_queue),
                runs_path=str(tmp_root / "runs.jsonl"),
                evaluations_path=str(tmp_root / "evaluations.jsonl"),
                report_dir=str(tmp_root / "reports"),
                run_preflight=False,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(report["overall_status"], "failed")
            self.assertTrue(report_path.is_file())
            self.assertTrue(report["summary"]["errors"])
            self.assertIn("queue file not found", report["summary"]["errors"][0])

    def test_null_execution_is_converted_to_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            spec_path = tmp_root / "spec.md"
            spec_path.write_text("content\n", encoding="utf-8")
            queue_path = tmp_root / "night-queue.yaml"
            queue_path.write_text(
                f"""\
mode: night-v0.1
max_tasks: 1
max_commits: 1
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources:
  - issue: 100
    spec: {spec_path}
""",
                encoding="utf-8",
            )

            with (
                patch("supervisor.night_executor.execute_night_task", return_value=None),
                patch(
                    "supervisor.night_executor.check_and_consume",
                    return_value={"allowed": True, "reason": "allowed"},
                ),
            ):
                exit_code, report, _ = run_night_executor(
                    queue_path=str(queue_path),
                    runs_path=str(tmp_root / "runs.jsonl"),
                    evaluations_path=str(tmp_root / "evaluations.jsonl"),
                    report_dir=str(tmp_root / "reports"),
                    run_preflight=False,
                )

            self.assertEqual(exit_code, 1)
            attempt = report["tasks"][0]["attempts"][0]
            self.assertEqual(attempt["run_status"], "failure")
            self.assertEqual(attempt["run_reason"], "null_execution")

    def test_autonomy_dryrun_generates_deterministic_proposals_and_skips_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            runs_path = tmp_root / "runs.jsonl"
            evaluations_path = tmp_root / "evaluations.jsonl"
            runs_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "run_id": "r1",
                                "task_id": "task-a",
                                "status": "failure",
                                "reason": "timeout",
                                "ts_start_ms": 0,
                                "ts_end_ms": 100,
                            }
                        ),
                        json.dumps(
                            {
                                "run_id": "r2",
                                "task_id": "task-b",
                                "status": "failure",
                                "reason": "timeout",
                                "ts_start_ms": 0,
                                "ts_end_ms": 120,
                            }
                        ),
                        json.dumps(
                            {
                                "run_id": "r3",
                                "task_id": "task-c",
                                "status": "failure",
                                "reason": "timeout",
                                "ts_start_ms": 0,
                                "ts_end_ms": 130,
                            }
                        ),
                        json.dumps(
                            {
                                "run_id": "r4",
                                "task_id": "task-d",
                                "status": "success",
                                "ts_start_ms": 0,
                                "ts_end_ms": 1000,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            evaluations_path.write_text("", encoding="utf-8")
            queue_path = tmp_root / "night-queue.yaml"
            queue_path.write_text(
                """\
mode: night-autonomy-dryrun-v0.1
max_tasks: 3
max_commits: 1
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
""",
                encoding="utf-8",
            )
            report_dir = tmp_root / "reports"
            before_runs = runs_path.read_text(encoding="utf-8")
            before_evaluations = evaluations_path.read_text(encoding="utf-8")

            original_cwd = os.getcwd()
            os.chdir(tmp_root)
            try:
                exit_code, report_a, _ = run_night_executor(
                    queue_path=str(queue_path),
                    runs_path=str(runs_path),
                    evaluations_path=str(evaluations_path),
                    report_dir=str(report_dir),
                    run_preflight=False,
                )
                proposals_a = report_a["autonomy"]["proposals_generated"]
                contents_a = {
                    p["filename"]: Path(p["path"]).read_text(encoding="utf-8")
                    for p in proposals_a
                }
                exit_code_b, report_b, _ = run_night_executor(
                    queue_path=str(queue_path),
                    runs_path=str(runs_path),
                    evaluations_path=str(evaluations_path),
                    report_dir=str(report_dir),
                    run_preflight=False,
                )
                proposals_b = report_b["autonomy"]["proposals_generated"]
                contents_b = {
                    p["filename"]: Path(p["path"]).read_text(encoding="utf-8")
                    for p in proposals_b
                }
            finally:
                os.chdir(original_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(exit_code_b, 0)
            self.assertEqual(report_a["overall_status"], "dryrun_complete")
            self.assertEqual(report_a["summary"]["tasks_attempted"], 0)
            self.assertEqual(report_a["summary"]["commits_performed"], 0)
            self.assertGreater(len(report_a["autonomy"]["proposals_generated"]), 0)
            self.assertEqual(proposals_a, proposals_b)
            self.assertEqual(contents_a, contents_b)
            self.assertEqual(before_runs, runs_path.read_text(encoding="utf-8"))
            self.assertEqual(before_evaluations, evaluations_path.read_text(encoding="utf-8"))

    def test_autonomy_promote_mode_generates_proposals_and_skips_task_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            runs_path = tmp_root / "runs.jsonl"
            evaluations_path = tmp_root / "evaluations.jsonl"
            runs_path.write_text("", encoding="utf-8")
            evaluations_path.write_text("", encoding="utf-8")
            queue_path = tmp_root / "night-queue.yaml"
            queue_path.write_text(
                """\
mode: night-autonomy-promote-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
""",
                encoding="utf-8",
            )
            report_dir = tmp_root / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (tmp_root / "ledger").mkdir(parents=True, exist_ok=True)
            root_before = sorted(p.name for p in tmp_root.iterdir())

            captured_proposals: list[dict] = []

            def _fake_promote(*_args, **kwargs):  # type: ignore[no-untyped-def]
                captured_proposals.extend(kwargs.get("proposals", []))
                return [{"status": "existing", "pr_number": 10}]

            with (
                patch(
                    "supervisor.night_executor.analyze_ledger",
                    return_value=[{"type": "repeated_failure", "reason": "timeout", "count": 3}],
                ),
                patch(
                    "supervisor.night_executor.create_draft_proposals_prs",
                    side_effect=_fake_promote,
                ),
            ):
                original_cwd = os.getcwd()
                os.chdir(tmp_root)
                try:
                    exit_code, report, _ = run_night_executor(
                        queue_path=str(queue_path),
                        runs_path=str(runs_path),
                        evaluations_path=str(evaluations_path),
                        report_dir=str(report_dir),
                        run_preflight=False,
                    )
                finally:
                    os.chdir(original_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(report["overall_status"], "promote_complete")
            self.assertEqual(report["summary"]["tasks_attempted"], 0)
            self.assertEqual(report["summary"]["commits_performed"], 0)
            self.assertEqual(len(report["autonomy"]["proposals_generated"]), 1)
            self.assertEqual(len(report["autonomy"]["promotion"]), 1)
            self.assertGreater(len(captured_proposals), 0)
            self.assertFalse((tmp_root / "docs").exists())
            root_after = sorted(p.name for p in tmp_root.iterdir())
            self.assertEqual(root_before, root_after)

    def test_autonomy_intake_mode_runs_review_intake_and_skips_task_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            runs_path = tmp_root / "runs.jsonl"
            evaluations_path = tmp_root / "evaluations.jsonl"
            runs_path.write_text("", encoding="utf-8")
            evaluations_path.write_text("", encoding="utf-8")
            queue_path = tmp_root / "night-queue.yaml"
            queue_path.write_text(
                """\
mode: night-autonomy-intake-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
""",
                encoding="utf-8",
            )
            report_dir = tmp_root / "reports"

            with patch(
                "supervisor.night_executor.intake_approved_autonomy_proposals",
                return_value=[{"pr_number": 11, "status": "intake_processed"}],
            ):
                exit_code, report, _ = run_night_executor(
                    queue_path=str(queue_path),
                    runs_path=str(runs_path),
                    evaluations_path=str(evaluations_path),
                    report_dir=str(report_dir),
                    run_preflight=False,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(report["overall_status"], "intake_complete")
            self.assertEqual(report["summary"]["tasks_attempted"], 0)
            self.assertEqual(report["summary"]["commits_performed"], 0)
            self.assertEqual(len(report["autonomy"]["intake"]), 1)


if __name__ == "__main__":
    unittest.main()

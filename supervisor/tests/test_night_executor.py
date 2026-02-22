from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor.night_executor import load_queue
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
    def test_queue_schema_validation_rejects_missing_required_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            queue_path = Path(tmp_dir) / "night-queue.yaml"
            queue_path.write_text("mode: night-v0.1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_queue(queue_path)

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

            with patch("supervisor.night_executor.execute_night_task", return_value=None):
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


if __name__ == "__main__":
    unittest.main()

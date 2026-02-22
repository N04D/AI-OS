from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor.night_task_runner import execute_night_task


class NightTaskRunnerTests(unittest.TestCase):
    def test_spec_missing_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "does-not-exist.md"
            result = execute_night_task(issue=12, spec_path=str(missing))
            self.assertEqual(result["status"], "failure")
            self.assertEqual(result["reason"], "spec_missing")
            self.assertIsInstance(result["ts_start_ms"], int)
            self.assertIsInstance(result["ts_end_ms"], int)
            self.assertGreaterEqual(result["ts_end_ms"], result["ts_start_ms"])

    def test_successful_dummy_execution(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "night-noop-spec.md"
        self.assertTrue(fixture.is_file())

        with patch(
            "supervisor.night_task_runner._execute_via_task_engine",
            return_value={
                "status": "success",
                "reason": None,
                "stdout": "ok",
                "stderr": "",
                "changed_files": [],
                "tests_passed": True,
                "dispatch_timestamp": "2026-02-22T00:00:00Z",
                "permit_usage_event_id": "evt-1",
            },
        ):
            result = execute_night_task(issue=42, spec_path=str(fixture))

        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["reason"])
        self.assertEqual(result["dispatch_timestamp"], "2026-02-22T00:00:00Z")
        self.assertEqual(result["permit_usage_event_id"], "evt-1")
        self.assertIsInstance(result["ts_start_ms"], int)
        self.assertIsInstance(result["ts_end_ms"], int)
        self.assertGreaterEqual(result["ts_end_ms"], result["ts_start_ms"])

    def test_engine_failure_is_structured_and_not_executor_not_wired(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "night-noop-spec.md"
        self.assertTrue(fixture.is_file())

        with patch(
            "supervisor.night_task_runner._execute_via_task_engine",
            return_value={
                "status": "failure",
                "reason": "execution.dispatch.nondeterministic",
                "stdout": "",
                "stderr": "",
                "changed_files": [],
                "tests_passed": False,
            },
        ):
            result = execute_night_task(issue=42, spec_path=str(fixture))

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["reason"], "execution.dispatch.nondeterministic")
        self.assertNotEqual(result["reason"], "executor_not_wired")


if __name__ == "__main__":
    unittest.main()

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
        with tempfile.TemporaryDirectory() as tmp_dir:
            spec = Path(tmp_dir) / "spec.md"
            spec.write_text("ok\n", encoding="utf-8")

            def _dummy_entrypoint(*, spec_path: str, issue: int) -> dict:
                self.assertEqual(spec_path, str(spec))
                self.assertEqual(issue, 42)
                return {
                    "status": "success",
                    "reason": None,
                    "stdout": "done",
                    "changed_files": [],
                    "tests_passed": True,
                }

            with patch(
                "supervisor.night_task_runner._discover_supervised_entrypoint",
                return_value=_dummy_entrypoint,
            ):
                result = execute_night_task(issue=42, spec_path=str(spec))

            self.assertEqual(result["status"], "success")
            self.assertIsNone(result["reason"])
            self.assertIsInstance(result["ts_start_ms"], int)
            self.assertIsInstance(result["ts_end_ms"], int)
            self.assertGreaterEqual(result["ts_end_ms"], result["ts_start_ms"])


if __name__ == "__main__":
    unittest.main()

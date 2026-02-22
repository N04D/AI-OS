from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from supervisor.autonomy_observer import analyze_ledger


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


class AutonomyObserverTests(unittest.TestCase):
    def test_detects_expected_opportunities_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            runs = tmp / "runs.jsonl"
            evaluations = tmp / "evaluations.jsonl"

            _write_jsonl(
                runs,
                [
                    {
                        "run_id": "r1",
                        "task_id": "task-a",
                        "status": "failure",
                        "reason": "timeout",
                        "ts_start_ms": 0,
                        "ts_end_ms": 100,
                    },
                    {
                        "run_id": "r2",
                        "task_id": "task-b",
                        "status": "failure",
                        "reason": "timeout",
                        "ts_start_ms": 0,
                        "ts_end_ms": 120,
                    },
                    {
                        "run_id": "r3",
                        "task_id": "task-c",
                        "status": "failure",
                        "reason": "timeout",
                        "ts_start_ms": 0,
                        "ts_end_ms": 130,
                    },
                    {
                        "run_id": "r4",
                        "task_id": "task-d",
                        "status": "success",
                        "ts_start_ms": 0,
                        "ts_end_ms": 1000,
                    },
                    {
                        "run_id": "r5",
                        "task_id": "task-e",
                        "status": "success",
                        "ts_start_ms": 0,
                        "ts_end_ms": 100,
                    },
                ],
            )
            _write_jsonl(
                evaluations,
                [
                    {
                        "run_id": "r5",
                        "task_id": "task-e",
                        "evaluation_result": "success",
                        "commit_performed": True,
                        "timestamp": "2026-02-22T00:00:00Z",
                    }
                ],
            )

            result = analyze_ledger(str(runs), str(evaluations))

            self.assertEqual(
                result,
                [
                    {
                        "type": "repeated_failure",
                        "reason": "timeout",
                        "count": 3,
                        "confidence": 0.8,
                    },
                    {
                        "type": "success_without_commit",
                        "task_id": "task-d",
                        "confidence": 0.75,
                    },
                    {
                        "type": "duration_outlier",
                        "task_id": "task-d",
                        "task_avg_duration_ms": 1000,
                        "global_avg_duration_ms": 290,
                        "confidence": 0.7,
                    },
                ],
            )

    def test_missing_ledgers_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            result = analyze_ledger(str(tmp / "missing-runs.jsonl"), str(tmp / "missing-evals.jsonl"))
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

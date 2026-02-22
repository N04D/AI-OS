from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from supervisor.ledger import ingest_evaluation_record_linked
from supervisor.results import ingest_run_record


class LedgerLinkageTests(unittest.TestCase):
    def test_evaluation_ingest_rejects_when_run_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            runs_path = tmp_path / "runs.jsonl"
            evaluations_path = tmp_path / "evaluations.jsonl"
            evaluation = {
                "run_id": "run-missing",
                "task_id": "123",
                "evaluation_result": "rejected",
                "timestamp": "2026-02-22T00:00:00Z",
            }

            result = ingest_evaluation_record_linked(evaluations_path, runs_path, evaluation)
            self.assertEqual(result["status"], "missing_run")
            self.assertEqual(result["reason"], "missing_run_record_for_evaluation")
            self.assertFalse(evaluations_path.exists())

    def test_evaluation_ingest_allows_when_run_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            runs_path = tmp_path / "runs.jsonl"
            evaluations_path = tmp_path / "evaluations.jsonl"
            run = {
                "version": "v0.1",
                "run_id": "run-ok",
                "task_id": "124",
                "attempt_no": 1,
                "env_fingerprint": "env",
                "task_spec_hash": "spec",
                "status": "success",
                "stdout": "",
                "stderr": "",
                "ts_start_ms": 1,
                "ts_end_ms": 2,
            }
            ingest_run_record(runs_path, run)
            evaluation = {
                "run_id": "run-ok",
                "task_id": "124",
                "evaluation_result": "success",
                "timestamp": "2026-02-22T00:00:01Z",
            }

            result = ingest_evaluation_record_linked(evaluations_path, runs_path, evaluation)
            self.assertEqual(result["status"], "ingested")
            rows = [line for line in evaluations_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0]), evaluation)


if __name__ == "__main__":
    unittest.main()

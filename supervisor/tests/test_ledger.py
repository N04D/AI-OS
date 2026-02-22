from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from supervisor.ledger import compute_run_id
from supervisor.ledger import find_evaluation_by_run_id
from supervisor.ledger import ingest_evaluation_record
from supervisor.ledger import is_run_committed


class LedgerIngestionTests(unittest.TestCase):
    def test_compute_run_id_stable(self) -> None:
        run_id_a = compute_run_id("task-1", "spec-hash", "env-hash", 1)
        run_id_b = compute_run_id("task-1", "spec-hash", "env-hash", 1)
        expected = hashlib.sha256(
            "v0.1|task-1|spec-hash|env-hash|1".encode("utf-8")
        ).hexdigest()
        self.assertEqual(run_id_a, run_id_b)
        self.assertEqual(run_id_a, expected)

    def test_ingest_idempotent_no_duplicate_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            record = {
                "run_id": compute_run_id("task-2", "spec-a", "env-a", 1),
                "task_id": "task-2",
                "evaluation_result": "accepted",
                "timestamp": "2026-02-22T00:00:00Z",
                "extra_field": "kept",
            }
            first = ingest_evaluation_record(ledger_path, record)
            second = ingest_evaluation_record(ledger_path, record)
            self.assertEqual(first["status"], "ingested")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(second["existing"], record)
            lines = [
                line
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), record)

    def test_find_returns_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            record_1 = {
                "run_id": compute_run_id("task-3", "spec-a", "env-a", 1),
                "task_id": "task-3",
                "evaluation_result": "accepted",
                "timestamp": "2026-02-22T00:00:01Z",
            }
            record_2 = {
                "run_id": compute_run_id("task-4", "spec-b", "env-b", 1),
                "task_id": "task-4",
                "evaluation_result": "rejected",
                "timestamp": "2026-02-22T00:00:02Z",
            }
            ingest_evaluation_record(ledger_path, record_1)
            ingest_evaluation_record(ledger_path, record_2)
            found = find_evaluation_by_run_id(ledger_path, record_2["run_id"])
            missing = find_evaluation_by_run_id(ledger_path, "does-not-exist")
            self.assertEqual(found, record_2)
            self.assertIsNone(missing)

    def test_is_run_committed_false_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            run_id = compute_run_id("task-5", "spec-a", "env-a", 1)
            self.assertFalse(is_run_committed(ledger_path, run_id))

    def test_is_run_committed_true_when_commit_performed_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            run_id = compute_run_id("task-6", "spec-a", "env-a", 1)
            record = {
                "run_id": run_id,
                "task_id": "task-6",
                "evaluation_result": "success",
                "timestamp": "2026-02-22T00:00:03Z",
                "commit_performed": True,
            }
            ingest_evaluation_record(ledger_path, record)
            self.assertTrue(is_run_committed(ledger_path, run_id))

    def test_commit_guard_blocks_second_commit_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            run_id = compute_run_id("task-7", "spec-a", "env-a", 1)
            first_success = {
                "run_id": run_id,
                "task_id": "task-7",
                "evaluation_result": "success",
                "timestamp": "2026-02-22T00:00:04Z",
                "commit_performed": True,
                "commit_sha": "abc1234",
            }
            ingest_evaluation_record(ledger_path, first_success)
            self.assertTrue(is_run_committed(ledger_path, run_id))

            second_attempt_rejection = {
                "run_id": run_id,
                "task_id": "task-7",
                "evaluation_result": "rejected",
                "timestamp": "2026-02-22T00:00:05Z",
                "commit_performed": False,
            }
            second = ingest_evaluation_record(ledger_path, second_attempt_rejection)
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(second["existing"]["evaluation_result"], "success")


if __name__ == "__main__":
    unittest.main()

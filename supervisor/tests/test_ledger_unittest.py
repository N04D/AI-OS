from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from supervisor.ledger import compute_run_id
from supervisor.ledger import find_evaluation_by_run_id
from supervisor.ledger import ingest_evaluation_record


class LedgerIngestionTests(unittest.TestCase):
    def test_compute_run_id_stable(self) -> None:
        a = compute_run_id("task-u1", "spec-hash", "env-hash", 1)
        b = compute_run_id("task-u1", "spec-hash", "env-hash", 1)
        self.assertEqual(a, b)

    def test_ingest_idempotent_no_duplicate_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            record = {
                "run_id": compute_run_id("task-u2", "spec-a", "env-a", 1),
                "task_id": "task-u2",
                "evaluation_result": "accepted",
                "timestamp": "2026-02-22T00:00:00Z",
                "extra": True,
            }

            first = ingest_evaluation_record(ledger_path, record)
            second = ingest_evaluation_record(ledger_path, record)
            self.assertEqual(first["status"], "ingested")
            self.assertEqual(second["status"], "duplicate")

            lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), record)

    def test_find_returns_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "evaluations.jsonl"
            record = {
                "run_id": compute_run_id("task-u3", "spec-a", "env-a", 1),
                "task_id": "task-u3",
                "evaluation_result": "rejected",
                "timestamp": "2026-02-22T00:00:00Z",
            }
            ingest_evaluation_record(ledger_path, record)

            found = find_evaluation_by_run_id(ledger_path, record["run_id"])
            missing = find_evaluation_by_run_id(ledger_path, "missing")
            self.assertEqual(found, record)
            self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()


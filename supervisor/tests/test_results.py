from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from supervisor.results import find_run_by_id
from supervisor.results import ingest_run_record
from supervisor.results import validate_exec_result_min


def _base_record() -> dict:
    return {
        "version": "v0.1",
        "run_id": "run-1",
        "task_id": "101",
        "attempt_no": 1,
        "env_fingerprint": "env-fingerprint",
        "task_spec_hash": "spec-hash",
        "status": "success",
        "stdout": "",
        "stderr": "",
        "ts_start_ms": 1,
        "ts_end_ms": 2,
    }


class ResultsLedgerTests(unittest.TestCase):
    def test_validation_rejects_missing_required_keys(self) -> None:
        record = _base_record()
        record.pop("status")
        with self.assertRaises(ValueError):
            validate_exec_result_min(record)

    def test_ingestion_idempotent_by_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "runs.jsonl"
            record = _base_record()
            first = ingest_run_record(ledger_path, record)
            second = ingest_run_record(ledger_path, record)
            self.assertEqual(first["status"], "ingested")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(second["existing"], record)
            lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), record)

    def test_find_returns_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "runs.jsonl"
            record = _base_record()
            record["run_id"] = "run-2"
            ingest_run_record(ledger_path, record)
            found = find_run_by_id(ledger_path, "run-2")
            missing = find_run_by_id(ledger_path, "missing")
            self.assertEqual(found, record)
            self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from supervisor.ledger import compute_run_id
from supervisor.ledger import find_evaluation_by_run_id
from supervisor.ledger import ingest_evaluation_record
from supervisor.ledger import is_run_committed


def test_compute_run_id_stable() -> None:
    a = compute_run_id("task-1", "spec-hash", "env-hash", 1)
    b = compute_run_id("task-1", "spec-hash", "env-hash", 1)
    expected = hashlib.sha256("v0.1|task-1|spec-hash|env-hash|1".encode("utf-8")).hexdigest()

    assert a == b
    assert a == expected


def test_ingest_idempotent_no_duplicate_lines(tmp_path: Path) -> None:
    ledger_path = tmp_path / "evaluations.jsonl"
    record = {
        "run_id": compute_run_id("task-2", "spec-a", "env-a", 1),
        "task_id": "task-2",
        "evaluation_result": "accepted",
        "timestamp": "2026-02-22T00:00:00Z",
        "extra_field": "kept",
    }

    first = ingest_evaluation_record(ledger_path, record)
    second = ingest_evaluation_record(ledger_path, record)

    assert first["status"] == "ingested"
    assert second["status"] == "duplicate"
    assert second["existing"] == record

    lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0]) == record


def test_find_returns_existing(tmp_path: Path) -> None:
    ledger_path = tmp_path / "evaluations.jsonl"
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

    assert found == record_2
    assert missing is None


def test_is_run_committed_false_when_missing(tmp_path: Path) -> None:
    ledger_path = tmp_path / "evaluations.jsonl"
    run_id = compute_run_id("task-5", "spec-a", "env-a", 1)
    assert is_run_committed(ledger_path, run_id) is False


def test_is_run_committed_true_when_commit_performed_true(tmp_path: Path) -> None:
    ledger_path = tmp_path / "evaluations.jsonl"
    run_id = compute_run_id("task-6", "spec-a", "env-a", 1)
    record = {
        "run_id": run_id,
        "task_id": "task-6",
        "evaluation_result": "success",
        "timestamp": "2026-02-22T00:00:03Z",
        "commit_performed": True,
    }
    ingest_evaluation_record(ledger_path, record)
    assert is_run_committed(ledger_path, run_id) is True


def test_commit_guard_blocks_second_commit_attempt(tmp_path: Path) -> None:
    ledger_path = tmp_path / "evaluations.jsonl"
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
    assert is_run_committed(ledger_path, run_id) is True

    second_attempt_rejection = {
        "run_id": run_id,
        "task_id": "task-7",
        "evaluation_result": "rejected",
        "timestamp": "2026-02-22T00:00:05Z",
        "commit_performed": False,
    }
    second = ingest_evaluation_record(ledger_path, second_attempt_rejection)
    assert second["status"] == "duplicate"
    assert second["existing"]["evaluation_result"] == "success"

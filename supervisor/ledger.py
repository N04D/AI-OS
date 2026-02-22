from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


REQUIRED_KEYS = ("run_id", "task_id", "evaluation_result", "timestamp")


def compute_run_id(
    task_id: str,
    task_spec_hash: str,
    env_fingerprint: str,
    attempt_no: int,
) -> str:
    payload = f"v0.1|{task_id}|{task_spec_hash}|{env_fingerprint}|{attempt_no}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_evaluation_by_run_id(path: str | os.PathLike[str], run_id: str) -> dict[str, Any] | None:
    ledger_path = Path(path)
    if not ledger_path.exists():
        return None

    with ledger_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("run_id") == run_id:
                return row
    return None


def ingest_evaluation_record(path: str | os.PathLike[str], record: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_KEYS if key not in record]
    if missing:
        raise ValueError(f"missing required keys: {', '.join(missing)}")

    ledger_path = Path(path)
    existing = find_evaluation_by_run_id(ledger_path, str(record["run_id"]))
    if existing is not None:
        return {"status": "duplicate", "existing": existing}

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())

    return {"status": "ingested", "record": record}


def is_run_committed(path: str | os.PathLike[str], run_id: str) -> bool:
    record = find_evaluation_by_run_id(path, run_id)
    if record is None:
        return False
    return bool(record.get("commit_performed") is True)


def mark_run_committed(path: str | os.PathLike[str], record: dict[str, Any]) -> dict[str, Any]:
    committed_record = dict(record)
    committed_record["commit_performed"] = True
    return ingest_evaluation_record(path, committed_record)

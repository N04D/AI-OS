from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REQUIRED_EXEC_RESULT_KEYS = (
    "version",
    "run_id",
    "task_id",
    "attempt_no",
    "env_fingerprint",
    "task_spec_hash",
    "status",
    "stdout",
    "stderr",
    "ts_start_ms",
    "ts_end_ms",
)


def validate_exec_result_min(record: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_EXEC_RESULT_KEYS if key not in record]
    if missing:
        raise ValueError(f"missing required keys: {', '.join(missing)}")


def find_run_by_id(path: str | os.PathLike[str], run_id: str) -> dict[str, Any] | None:
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


def ingest_run_record(path: str | os.PathLike[str], record: dict[str, Any]) -> dict[str, Any]:
    validate_exec_result_min(record)

    ledger_path = Path(path)
    existing = find_run_by_id(ledger_path, str(record["run_id"]))
    if existing is not None:
        return {"status": "duplicate", "existing": existing}

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())

    return {"status": "ingested", "record": record}

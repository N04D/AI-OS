from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_LOG_PATH = Path("logs/control/nightly_dispatch_audit.jsonl")


class AuditEventError(RuntimeError):
    pass


def utc_iso(now_utc: datetime | None = None) -> str:
    now = now_utc.astimezone(UTC) if isinstance(now_utc, datetime) else datetime.now(UTC)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def emit_audit_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(event_type, str) or not event_type.strip():
        raise AuditEventError("event_type_invalid")
    if not isinstance(payload, dict):
        raise AuditEventError("payload_invalid")

    record = {
        "ts_utc": utc_iso(now_utc),
        "event_type": event_type.strip(),
        "payload": payload,
    }
    try:
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_log_path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(record) + "\n")
    except Exception as exc:
        raise AuditEventError(f"audit_write_failed:{exc}") from exc
    return record

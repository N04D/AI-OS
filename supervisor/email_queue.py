from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any

from supervisor.audit_events import emit_audit_event


DEFAULT_QUEUE_ROOT = Path("state/email_queue")
DEFAULT_AUDIT_LOG_PATH = Path("logs/control/nightly_dispatch_audit.jsonl")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_Z_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_QUEUE_KEYS = {"scheduled_at_utc", "idempotency_key", "report_path", "report_hash", "status"}
_STATUS_VALUES = {"pending", "sent", "failed"}


class EmailQueueError(RuntimeError):
    pass


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_utc_offset(offset: str) -> timezone:
    text = str(offset or "").strip()
    match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", text)
    if not match:
        raise EmailQueueError("operator_utc_offset_invalid")
    sign = 1 if match.group(1) == "+" else -1
    hours = int(match.group(2))
    minutes = int(match.group(3))
    if hours > 23 or minutes > 59:
        raise EmailQueueError("operator_utc_offset_invalid")
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def _scheduled_utc_iso(local_date: str, operator_utc_offset: str) -> str:
    if not _DATE_RE.fullmatch(local_date):
        raise EmailQueueError("local_date_invalid")
    tz = _parse_utc_offset(operator_utc_offset)
    local_dt = datetime.strptime(local_date + " 09:30:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
    utc_dt = local_dt.astimezone(UTC)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_queue_schema(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise EmailQueueError("queue_payload_invalid")
    if set(payload.keys()) != _QUEUE_KEYS:
        raise EmailQueueError("queue_schema_keys_invalid")
    scheduled = payload.get("scheduled_at_utc")
    if not isinstance(scheduled, str) or not _Z_TS_RE.fullmatch(scheduled):
        raise EmailQueueError("queue_scheduled_at_utc_invalid")
    idem = payload.get("idempotency_key")
    if not isinstance(idem, str) or not _SHA256_RE.fullmatch(idem):
        raise EmailQueueError("queue_idempotency_key_invalid")
    report_path = payload.get("report_path")
    if not isinstance(report_path, str) or not report_path.strip():
        raise EmailQueueError("queue_report_path_invalid")
    report_hash = payload.get("report_hash")
    if not isinstance(report_hash, str) or not _SHA256_RE.fullmatch(report_hash):
        raise EmailQueueError("queue_report_hash_invalid")
    status = payload.get("status")
    if status not in _STATUS_VALUES:
        raise EmailQueueError("queue_status_invalid")


def enqueue_morning_dispatch(
    *,
    date: str,
    report_path: str,
    report_hash: str,
    operator_utc_offset: str = "+00:00",
    queue_root: Path = DEFAULT_QUEUE_ROOT,
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH,
) -> dict[str, str]:
    if not _DATE_RE.fullmatch(str(date)):
        raise EmailQueueError("queue_date_invalid")
    if not isinstance(report_path, str) or not report_path.strip():
        raise EmailQueueError("queue_report_path_invalid")
    if not isinstance(report_hash, str) or not _SHA256_RE.fullmatch(report_hash):
        raise EmailQueueError("queue_report_hash_invalid")

    scheduled_at_utc = _scheduled_utc_iso(date, operator_utc_offset)
    idempotency_source = f"{date}|{scheduled_at_utc}|{report_path}|{report_hash}"
    idempotency_key = _sha256_text(idempotency_source)

    payload = {
        "scheduled_at_utc": scheduled_at_utc,
        "idempotency_key": idempotency_key,
        "report_path": report_path,
        "report_hash": report_hash,
        "status": "pending",
    }
    validate_queue_schema(payload)

    queue_path = queue_root / f"{date}__0930.json"
    queue_text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    try:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        if queue_path.exists():
            current = json.loads(queue_path.read_text(encoding="utf-8"))
            validate_queue_schema(current)
            if current != payload:
                raise EmailQueueError("queue_item_conflict_existing_payload")
        queue_path.write_text(queue_text, encoding="utf-8")
    except EmailQueueError:
        raise
    except Exception as exc:
        raise EmailQueueError(f"queue_write_failed:{exc}") from exc

    emit_audit_event(
        "queue_enqueued",
        {
            "date": date,
            "queue_path": str(queue_path),
            "idempotency_key": idempotency_key,
            "scheduled_at_utc": scheduled_at_utc,
            "report_path": report_path,
            "report_hash": report_hash,
        },
        audit_log_path=audit_log_path,
    )
    return {"queue_path": str(queue_path), "idempotency_key": idempotency_key}

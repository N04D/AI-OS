from __future__ import annotations

import hashlib
import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from supervisor.audit_events import emit_audit_event
from supervisor.email_queue import DEFAULT_QUEUE_ROOT
from supervisor.email_queue import EmailQueueError
from supervisor.email_queue import validate_queue_schema


DEFAULT_LEDGER_PATH = Path("state/email_ledger.json")
DEFAULT_AUDIT_LOG_PATH = Path("logs/control/nightly_dispatch_audit.jsonl")


class DispatchWorkerError(RuntimeError):
    pass


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_utc(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _utc_now(now_utc: datetime | None = None) -> datetime:
    if isinstance(now_utc, datetime):
        return now_utc.astimezone(UTC)
    return datetime.now(UTC)


def _load_ledger(ledger_path: Path) -> dict[str, Any]:
    if not ledger_path.exists():
        return {"sent_keys": []}
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DispatchWorkerError("email_ledger_invalid_json") from exc
    if not isinstance(payload, dict):
        raise DispatchWorkerError("email_ledger_invalid_type")
    sent_keys = payload.get("sent_keys")
    if not isinstance(sent_keys, list) or any(not isinstance(item, str) or not item.strip() for item in sent_keys):
        raise DispatchWorkerError("email_ledger_invalid_sent_keys")
    return {"sent_keys": sorted(set(sent_keys))}


def _write_ledger(ledger_path: Path, payload: dict[str, Any]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_queue_item(path: Path, payload: dict[str, Any]) -> None:
    validate_queue_schema(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def send_email_stub(*, queue_item: dict[str, Any], report_payload: dict[str, Any]) -> dict[str, Any]:
    # Deterministic no-network stub.
    digest = hashlib.sha256(_canonical_json(queue_item).encode("utf-8")).hexdigest()
    return {"ok": True, "transport": "stub", "message_id": f"stub-{digest[:16]}"}


def run_dispatch_worker(
    *,
    queue_root: Path = DEFAULT_QUEUE_ROOT,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now = _utc_now(now_utc)
    summary = {"processed": 0, "sent": 0, "failed": 0}

    ledger = _load_ledger(ledger_path)
    sent_keys = set(ledger["sent_keys"])

    queue_root.mkdir(parents=True, exist_ok=True)
    for queue_path in sorted(queue_root.glob("*.json")):
        summary["processed"] += 1
        try:
            queue_item = json.loads(queue_path.read_text(encoding="utf-8"))
            validate_queue_schema(queue_item)
            if queue_item["status"] != "pending":
                continue
            if _parse_utc(str(queue_item["scheduled_at_utc"])) > now:
                continue

            idempotency_key = str(queue_item["idempotency_key"])
            report_path = Path(str(queue_item["report_path"]))
            report_hash = str(queue_item["report_hash"])

            if idempotency_key in sent_keys:
                queue_item["status"] = "failed"
                _write_queue_item(queue_path, queue_item)
                emit_audit_event(
                    "dispatch_failed",
                    {
                        "queue_path": str(queue_path),
                        "idempotency_key": idempotency_key,
                        "reason_code": "DENY_DUPLICATE_IDEMPOTENCY_KEY",
                    },
                    audit_log_path=audit_log_path,
                    now_utc=now,
                )
                summary["failed"] += 1
                continue

            if not report_path.exists():
                queue_item["status"] = "failed"
                _write_queue_item(queue_path, queue_item)
                emit_audit_event(
                    "dispatch_failed",
                    {
                        "queue_path": str(queue_path),
                        "idempotency_key": idempotency_key,
                        "reason_code": "DENY_REPORT_MISSING",
                    },
                    audit_log_path=audit_log_path,
                    now_utc=now,
                )
                summary["failed"] += 1
                continue

            try:
                report_payload = json.loads(report_path.read_text(encoding="utf-8"))
                if not isinstance(report_payload, dict):
                    raise DispatchWorkerError("report_payload_invalid")
                actual_hash = _sha256_text(_canonical_json(report_payload))
            except Exception as exc:
                queue_item["status"] = "failed"
                _write_queue_item(queue_path, queue_item)
                emit_audit_event(
                    "dispatch_failed",
                    {
                        "queue_path": str(queue_path),
                        "idempotency_key": idempotency_key,
                        "reason_code": f"DENY_REPORT_PARSE_FAILED:{exc}",
                    },
                    audit_log_path=audit_log_path,
                    now_utc=now,
                )
                summary["failed"] += 1
                continue

            if actual_hash != report_hash:
                queue_item["status"] = "failed"
                _write_queue_item(queue_path, queue_item)
                emit_audit_event(
                    "dispatch_failed",
                    {
                        "queue_path": str(queue_path),
                        "idempotency_key": idempotency_key,
                        "reason_code": "DENY_REPORT_HASH_MISMATCH",
                        "actual_hash": actual_hash,
                        "expected_hash": report_hash,
                    },
                    audit_log_path=audit_log_path,
                    now_utc=now,
                )
                summary["failed"] += 1
                continue

            send_result = send_email_stub(queue_item=queue_item, report_payload=report_payload)
            if not bool(send_result.get("ok", False)):
                queue_item["status"] = "failed"
                _write_queue_item(queue_path, queue_item)
                emit_audit_event(
                    "dispatch_failed",
                    {
                        "queue_path": str(queue_path),
                        "idempotency_key": idempotency_key,
                        "reason_code": "DENY_SEND_STUB_FAILED",
                    },
                    audit_log_path=audit_log_path,
                    now_utc=now,
                )
                summary["failed"] += 1
                continue

            queue_item["status"] = "sent"
            _write_queue_item(queue_path, queue_item)
            sent_keys.add(idempotency_key)
            ledger["sent_keys"] = sorted(sent_keys)
            _write_ledger(ledger_path, ledger)
            emit_audit_event(
                "dispatch_sent",
                {
                    "queue_path": str(queue_path),
                    "idempotency_key": idempotency_key,
                    "message_id": str(send_result.get("message_id", "")),
                },
                audit_log_path=audit_log_path,
                now_utc=now,
            )
            summary["sent"] += 1

        except (DispatchWorkerError, EmailQueueError, json.JSONDecodeError) as exc:
            # Invalid queue files fail closed.
            emit_audit_event(
                "dispatch_failed",
                {
                    "queue_path": str(queue_path),
                    "reason_code": f"DENY_QUEUE_INVALID:{exc}",
                },
                audit_log_path=audit_log_path,
                now_utc=now,
            )
            summary["failed"] += 1
            continue

    return summary

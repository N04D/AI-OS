from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from supervisor.audit_events import emit_audit_event


DEFAULT_REPORT_ROOT = Path("state/reports/nightly")
DEFAULT_AUDIT_LOG_PATH = Path("logs/control/nightly_dispatch_audit.jsonl")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_REQUIRED_KEYS = {
    "date",
    "epoch",
    "summary",
    "tasks_executed",
    "failures",
    "budget_used",
    "stopped",
    "toolchain_hash",
}


class NightReportError(RuntimeError):
    pass


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_report_schema(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise NightReportError("report_payload_invalid")
    if set(payload.keys()) != _REQUIRED_KEYS:
        raise NightReportError("report_schema_keys_invalid")

    date = payload.get("date")
    if not isinstance(date, str) or not _DATE_RE.fullmatch(date):
        raise NightReportError("report_date_invalid")
    epoch = payload.get("epoch")
    if not isinstance(epoch, str) or not epoch.strip():
        raise NightReportError("report_epoch_invalid")
    summary = payload.get("summary")
    if not isinstance(summary, str):
        raise NightReportError("report_summary_invalid")
    tasks_executed = payload.get("tasks_executed")
    if not isinstance(tasks_executed, list):
        raise NightReportError("report_tasks_executed_invalid")
    failures = payload.get("failures")
    if not isinstance(failures, list):
        raise NightReportError("report_failures_invalid")
    budget_used = payload.get("budget_used")
    if not isinstance(budget_used, (int, float)):
        raise NightReportError("report_budget_used_invalid")
    stopped = payload.get("stopped")
    if not isinstance(stopped, bool):
        raise NightReportError("report_stopped_invalid")
    toolchain_hash = payload.get("toolchain_hash")
    if not isinstance(toolchain_hash, str) or not _SHA256_RE.fullmatch(toolchain_hash):
        raise NightReportError("report_toolchain_hash_invalid")


def write_nightly_report(
    payload: dict[str, Any],
    *,
    report_root: Path = DEFAULT_REPORT_ROOT,
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH,
) -> dict[str, str]:
    validate_report_schema(payload)
    date = str(payload["date"])
    report_path = report_root / f"{date}.json"
    report_text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    report_hash = _sha256_text(_canonical_json(payload))

    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        (report_root / f"{date}.json.sha256").write_text(report_hash + "\n", encoding="utf-8")
    except Exception as exc:
        raise NightReportError(f"report_write_failed:{exc}") from exc

    emit_audit_event(
        "report_generated",
        {
            "date": date,
            "epoch": str(payload["epoch"]),
            "report_path": str(report_path),
            "report_hash": report_hash,
        },
        audit_log_path=audit_log_path,
    )

    return {"report_path": str(report_path), "report_hash": report_hash}

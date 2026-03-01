from __future__ import annotations

import json
import os
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_CAPABILITY = "email.send"
REQUIRED_SECRETS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")
DEFAULT_CAPABILITY_REGISTRY_PATH = Path("state/capabilities/enabled.json")
DEFAULT_AUDIT_LOG_PATH = Path("logs/control/email_send_audit.jsonl")

DENY_EMAIL_CAPABILITY_MISSING = "DENY_CAPABILITY_MISSING"
DENY_EMAIL_SECRETS_MISSING = "DENY_EMAIL_SECRETS_MISSING"
DENY_EMAIL_NETWORK_UNAVAILABLE = "DENY_NETWORK_ACCESS_REQUIRED"
DENY_EMAIL_PAYLOAD_INVALID = "DENY_EMAIL_PAYLOAD_INVALID"
DENY_EMAIL_STATE_INVALID = "DENY_STATE_INVALID"


def _now_utc(now_utc: datetime | None = None) -> datetime:
    if isinstance(now_utc, datetime):
        return now_utc.astimezone(UTC)
    return datetime.now(UTC)


def _append_audit(audit_log_path: Path, payload: dict[str, Any]) -> None:
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def _load_enabled_capabilities(capability_registry_path: Path) -> set[str]:
    try:
        payload = json.loads(capability_registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("capability_registry_missing") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("capability_registry_invalid_json") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("capability_registry_invalid_type")
    enabled = payload.get("enabled")
    if not isinstance(enabled, list) or any(not isinstance(item, str) or not item.strip() for item in enabled):
        raise RuntimeError("capability_registry_invalid_enabled")
    return {item.strip() for item in enabled}


def _network_access_allowed() -> bool:
    value = (os.environ.get("NETWORK_ACCESS_ENABLED", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def run_email_send(
    payload: dict[str, Any],
    *,
    capability_registry_path: Path = DEFAULT_CAPABILITY_REGISTRY_PATH,
    audit_log_path: Path = DEFAULT_AUDIT_LOG_PATH,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now = _now_utc(now_utc)
    subject = payload.get("subject")
    body = payload.get("body")
    to = payload.get("to")
    if not isinstance(subject, str) or not subject.strip():
        return {"ok": False, "reason_code": DENY_EMAIL_PAYLOAD_INVALID, "detail": "subject missing"}
    if not isinstance(body, str) or not body.strip():
        return {"ok": False, "reason_code": DENY_EMAIL_PAYLOAD_INVALID, "detail": "body missing"}
    if not isinstance(to, str) or not to.strip():
        return {"ok": False, "reason_code": DENY_EMAIL_PAYLOAD_INVALID, "detail": "to missing"}

    try:
        enabled = _load_enabled_capabilities(capability_registry_path)
    except RuntimeError as exc:
        record = {
            "ts_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "capability": REQUIRED_CAPABILITY,
            "allowed": False,
            "reason_code": DENY_EMAIL_STATE_INVALID,
            "detail": str(exc),
        }
        _append_audit(audit_log_path, record)
        return {"ok": False, "reason_code": DENY_EMAIL_STATE_INVALID, "detail": str(exc)}

    if REQUIRED_CAPABILITY not in enabled:
        record = {
            "ts_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "capability": REQUIRED_CAPABILITY,
            "allowed": False,
            "reason_code": DENY_EMAIL_CAPABILITY_MISSING,
            "detail": "email.send not enabled",
        }
        _append_audit(audit_log_path, record)
        return {"ok": False, "reason_code": DENY_EMAIL_CAPABILITY_MISSING, "detail": "email.send not enabled"}

    missing_secrets = sorted([key for key in REQUIRED_SECRETS if not (os.environ.get(key, "") or "").strip()])
    if missing_secrets:
        record = {
            "ts_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "capability": REQUIRED_CAPABILITY,
            "allowed": False,
            "reason_code": DENY_EMAIL_SECRETS_MISSING,
            "missing": missing_secrets,
        }
        _append_audit(audit_log_path, record)
        return {"ok": False, "reason_code": DENY_EMAIL_SECRETS_MISSING, "missing": missing_secrets}

    if not _network_access_allowed():
        record = {
            "ts_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "capability": REQUIRED_CAPABILITY,
            "allowed": False,
            "reason_code": DENY_EMAIL_NETWORK_UNAVAILABLE,
            "detail": "NETWORK_ACCESS_ENABLED required",
        }
        _append_audit(audit_log_path, record)
        return {"ok": False, "reason_code": DENY_EMAIL_NETWORK_UNAVAILABLE, "detail": "NETWORK_ACCESS_ENABLED required"}

    record = {
        "ts_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "capability": REQUIRED_CAPABILITY,
        "allowed": True,
        "reason_code": None,
        "to": to.strip(),
        "subject": subject.strip(),
        "transport": "smtp",
    }
    _append_audit(audit_log_path, record)
    return {"ok": True, "transport": "smtp", "capability": REQUIRED_CAPABILITY}


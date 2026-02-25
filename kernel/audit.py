"""Kernel operator audit logging."""

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path


class AuditWriteError(Exception):
    pass


def _now_rfc3339_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def append_plugin_event(
    *,
    action: str,
    result: str,
    reason_code: str,
    details: list[str] | None = None,
    plugin_id: str | None = None,
    trust_tier: str | None = None,
    actor: str = "local-cli",
    audit_log_path: str | Path = "logs/control/plugin-events.jsonl",
) -> None:
    payload = {
        "action": action,
        "actor": actor,
        "details": details or [],
        "reason_code": reason_code,
        "result": result,
        "ts": _now_rfc3339_utc(),
    }
    if plugin_id is not None:
        payload["plugin_id"] = plugin_id
    if trust_tier is not None:
        payload["trust_tier"] = trust_tier

    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception as exc:
        raise AuditWriteError("AUDIT_LOG_WRITE_FAILED") from exc

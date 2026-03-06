"""Email ingress boundary that emits a single internal event from inbox artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import kernel.events as events

EVENT_TYPE = "channel.email.message"


def parse_inbox_artifact(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("email inbox artifact must be an object")
    subject = str(payload.get("subject", ""))
    body = str(payload.get("body", ""))
    if not subject and not body:
        raise ValueError("email inbox artifact must include subject or body")
    return payload


def emit_email_artifact(
    artifact_path: str | Path,
    *,
    registry_path: str = "state/plugins/registry.json",
    config_path: str = "state/plugins/config.json",
    audit_log_path: str = "logs/control/kernel-events.jsonl",
) -> dict[str, Any]:
    artifact = Path(artifact_path)
    record = parse_inbox_artifact(artifact)
    event_payload = {
        "channel": "email",
        "artifact_path": str(artifact),
        "agent": str(record.get("agent", "")),
        "from": str(record.get("from", "")),
        "to": str(record.get("to", "")),
        "subject": str(record.get("subject", "")),
        "body": str(record.get("body", "")),
        "uid": str(record.get("uid", "")),
        "epoch": str(record.get("epoch", "")),
    }
    return events.emit(
        EVENT_TYPE,
        event_payload,
        registry_path=registry_path,
        config_path=config_path,
        audit_log_path=audit_log_path,
    )

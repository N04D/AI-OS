"""Telegram ingress boundary that emits a single internal event."""

from __future__ import annotations

import hmac
import json
import os
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

import kernel.events as events
from kernel.channels.replay_cache import ReplayCache

EVENT_TYPE = "channel.telegram.message"

DENY_SECRET_MISSING = "DENY_SECRET_MISSING"
DENY_SECRET_INVALID = "DENY_SECRET_INVALID"
DENY_CHAT_NOT_ALLOWED = "DENY_CHAT_NOT_ALLOWED"
DENY_BAD_JSON = "DENY_BAD_JSON"
DENY_NO_MESSAGE = "DENY_NO_MESSAGE"
DENY_AUDIT_WRITE_FAILED = "DENY_AUDIT_WRITE_FAILED"
REPLAY_DETECTED = "REPLAY_DETECTED"

REPLAY_CACHE = ReplayCache()


def now_rfc3339_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_update(update: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(update, dict):
        return None
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    if not isinstance(text, str) or text == "":
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return None

    from_user = message.get("from")
    from_user_id = from_user.get("id") if isinstance(from_user, dict) else None
    if not isinstance(from_user_id, int):
        from_user_id = None

    message_id = message.get("message_id")
    if not isinstance(message_id, int):
        message_id = None

    date = message.get("date")
    if not isinstance(date, int):
        date = None

    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        return None

    return {
        "update_id": update_id,
        "message_id": message_id,
        "chat_id": chat_id,
        "from_user_id": from_user_id,
        "text": text,
        "date": date,
    }


def resolve_intent(message: str) -> tuple[str, dict[str, Any]] | None:
    """Resolve fixed Telegram intents in a deterministic, fail-closed way."""
    if not isinstance(message, str):
        return None
    text = " ".join(message.strip().split())
    if not text:
        return None

    # Command mode (strict)
    if text.startswith("/"):
        if text == "/status":
            return "status", {}
        if text.startswith("/send"):
            parts = text.split(" ", 2)
            if len(parts) != 3:
                return None
            if parts[0] != "/send":
                return None
            recipient = parts[1].strip()
            body = parts[2].strip()
            if not recipient or not body:
                return None
            return "send-message", {"recipient": recipient, "text": body}
        return None

    # Natural-language mode (limited pattern matching)
    lowered = text.casefold()
    has_send_later = "stuur" in lowered and "later" in lowered
    has_status = "status" in lowered

    if has_send_later and has_status:
        return None
    if has_send_later:
        payload: dict[str, Any] = {"text": text}
        marker = "naar "
        idx = lowered.find(marker)
        if idx != -1:
            recipient_raw = text[idx + len(marker) :].strip()
            recipient = recipient_raw.split(" ", 1)[0].strip(".,:;!?")
            if recipient:
                payload["recipient"] = recipient
        return "send-message", payload
    if has_status:
        return "status", {}
    return None


def authorize_secret(header_value: str | None, expected_secret: str | None) -> tuple[bool, str | None]:
    if not expected_secret:
        return False, DENY_SECRET_MISSING
    if not header_value:
        return False, DENY_SECRET_INVALID
    if not hmac.compare_digest(header_value, expected_secret):
        return False, DENY_SECRET_INVALID
    return True, None


def parse_allowed_chat_ids(value: str | None) -> set[int]:
    if not value:
        return set()
    out: set[int] = set()
    for token in value.split(","):
        item = token.strip()
        if not item:
            continue
        try:
            out.add(int(item))
        except ValueError:
            continue
    return out


def is_chat_allowed(chat_id: int, allowed_chat_ids: set[int]) -> bool:
    return chat_id in allowed_chat_ids


def ingress_audit(
    *,
    remote_ip: str | None,
    update_id: int | None,
    chat_id: int | None,
    result: str,
    reason_code: str,
    audit_log_path: str,
) -> None:
    payload = {
        "chat_id": chat_id,
        "reason_code": reason_code,
        "remote_ip": remote_ip,
        "result": result,
        "ts": now_rfc3339_utc(),
        "update_id": update_id,
    }
    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception as exc:
        raise RuntimeError(DENY_AUDIT_WRITE_FAILED) from exc


def replay_detected(
    *,
    remote_ip: str | None,
    update_id: int | None,
    chat_id: int | None,
    ingress_audit_log_path: str,
) -> bool:
    if REPLAY_CACHE.seen(update_id):
        ingress_audit(
            remote_ip=remote_ip,
            update_id=update_id,
            chat_id=chat_id,
            result="deny",
            reason_code=REPLAY_DETECTED,
            audit_log_path=ingress_audit_log_path,
        )
        return True
    return False


def emit_telegram_message(
    normalized_message: dict[str, Any],
    *,
    registry_path: str,
    config_path: str,
    audit_log_path: str,
) -> dict[str, Any]:
    update_id = normalized_message.get("update_id")
    payload = {
        "channel": "telegram",
        "update_id": update_id,
        "message_id": normalized_message.get("message_id"),
        "chat_id": normalized_message.get("chat_id"),
        "from_user_id": normalized_message.get("from_user_id"),
        "text": normalized_message.get("text"),
        "date": normalized_message.get("date"),
    }
    return events.emit(
        EVENT_TYPE,
        payload,
        registry_path=registry_path,
        config_path=config_path,
        audit_log_path=audit_log_path,
    )


def runtime_paths_from_env() -> dict[str, str]:
    return {
        "registry_path": os.getenv("AIOS_REGISTRY_PATH", "state/plugins/registry.json"),
        "config_path": os.getenv("AIOS_CONFIG_PATH", "state/plugins/config.json"),
        "event_audit_log_path": os.getenv("AIOS_EVENT_AUDIT_LOG_PATH", "logs/control/kernel-events.jsonl"),
        "telegram_ingress_audit_log_path": os.getenv(
            "AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH",
            "logs/control/channel-telegram.jsonl",
        ),
    }

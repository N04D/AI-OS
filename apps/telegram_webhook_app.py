"""FastAPI webhook ingress for Telegram updates."""

from __future__ import annotations

import os
import time
from datetime import UTC
from datetime import datetime

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from kernel.channels.telegram import DENY_AUDIT_WRITE_FAILED
from kernel.channels.telegram import DENY_BAD_JSON
from kernel.channels.telegram import DENY_CHAT_NOT_ALLOWED
from kernel.channels.telegram import DENY_NO_MESSAGE
from kernel.channels.telegram import authorize_secret
from kernel.channels.telegram import ingress_audit
from kernel.channels.telegram import is_chat_allowed
from kernel.channels.telegram import parse_allowed_chat_ids
from kernel.channels.telegram import parse_update
from kernel.channels.telegram import replay_detected
from kernel.channels.telegram import resolve_intent
from kernel.channels.telegram import runtime_paths_from_env
from kernel.channels.telegram_validation import validate_webhook_configuration
from kernel.plugins.config import PluginConfigError
from kernel.plugins.config import load_config
from kernel.skills import run_skill


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() == "true"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name}_REQUIRED_FOR_STARTUP_VALIDATION")
    return value


if _env_true("AIOS_VALIDATE_WEBHOOK_ON_STARTUP"):
    validate_webhook_configuration(
        bot_token=_require_env("AIOS_TELEGRAM_BOT_TOKEN"),
        expected_url=_require_env("AIOS_TELEGRAM_WEBHOOK_URL"),
        expected_secret=_require_env("AIOS_TELEGRAM_WEBHOOK_SECRET"),
    )

app = FastAPI(title="AI-OS Telegram Webhook")
PROCESS_START_MONOTONIC = time.monotonic()
EVENTS_PROCESSED = 0
REPLAYS_BLOCKED = 0


def _now_rfc3339_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _plugins_enabled_count(config_path: str) -> int:
    config = load_config(config_path)
    enabled = config.get("enabled")
    if not isinstance(enabled, list):
        raise PluginConfigError("CONFIG_INVALID")
    return len([v for v in enabled if isinstance(v, str) and v])


def _plugins_unhealthy_count() -> int:
    # Runner unhealthy state is not persisted globally in current architecture.
    return 0


def _remote_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _safe_update_fields(update: object) -> tuple[int | None, int | None]:
    if not isinstance(update, dict):
        return None, None
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        update_id = None
    message = update.get("message")
    chat_id = None
    if isinstance(message, dict):
        chat = message.get("chat")
        if isinstance(chat, dict) and isinstance(chat.get("id"), int):
            chat_id = chat["id"]
    return update_id, chat_id


def _execution_response(
    *,
    ok: bool,
    executed: bool,
    skill_id: str | None,
    reply: str,
    result: object | None,
    error: object | None,
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "ok": ok,
            "executed": executed,
            "skill_id": skill_id,
            "reply": reply,
            "result": result,
            "error": error,
        },
    )


def _deny(
    *,
    request: Request,
    update_id: int | None,
    chat_id: int | None,
    reason_code: str,
    status_code: int,
    ingress_audit_log_path: str,
) -> JSONResponse:
    try:
        ingress_audit(
            remote_ip=_remote_ip(request),
            update_id=update_id,
            chat_id=chat_id,
            result="deny",
            reason_code=reason_code,
            audit_log_path=ingress_audit_log_path,
        )
    except RuntimeError:
        return JSONResponse(status_code=403, content={"ok": False, "reason_code": DENY_AUDIT_WRITE_FAILED})
    return JSONResponse(status_code=status_code, content={"ok": False, "reason_code": reason_code})


@app.get("/health")
async def health() -> JSONResponse:
    if _env_true("AIOS_VALIDATE_WEBHOOK_ON_STARTUP"):
        try:
            validate_webhook_configuration(
                bot_token=_require_env("AIOS_TELEGRAM_BOT_TOKEN"),
                expected_url=_require_env("AIOS_TELEGRAM_WEBHOOK_URL"),
                expected_secret=_require_env("AIOS_TELEGRAM_WEBHOOK_SECRET"),
            )
        except Exception:
            return JSONResponse(status_code=200, content={"ok": False, "reason": "WEBHOOK_INVALID"})
    return JSONResponse(
        status_code=200,
        content={"ok": True, "service": "telegram-ingress", "timestamp": _now_rfc3339_utc()},
    )


@app.get("/metrics")
async def metrics() -> JSONResponse:
    paths = runtime_paths_from_env()
    uptime_seconds = int(max(0.0, time.monotonic() - PROCESS_START_MONOTONIC))
    try:
        plugins_enabled = _plugins_enabled_count(paths["config_path"])
        plugins_unhealthy = _plugins_unhealthy_count()
    except Exception:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "reason": "STATE_UNREADABLE",
                "uptime_seconds": uptime_seconds,
                "events_processed": EVENTS_PROCESSED,
                "replays_blocked": REPLAYS_BLOCKED,
                "plugins_enabled": 0,
                "plugins_unhealthy": 0,
            },
        )
    return JSONResponse(
        status_code=200,
        content={
            "uptime_seconds": uptime_seconds,
            "events_processed": EVENTS_PROCESSED,
            "replays_blocked": REPLAYS_BLOCKED,
            "plugins_enabled": plugins_enabled,
            "plugins_unhealthy": plugins_unhealthy,
        },
    )


@app.post("/webhook/telegram")
async def webhook_telegram(request: Request) -> JSONResponse:
    global EVENTS_PROCESSED
    global REPLAYS_BLOCKED
    paths = runtime_paths_from_env()
    ingress_audit_log_path = paths["telegram_ingress_audit_log_path"]

    try:
        update = await request.json()
    except Exception:
        return _deny(
            request=request,
            update_id=None,
            chat_id=None,
            reason_code=DENY_BAD_JSON,
            status_code=400,
            ingress_audit_log_path=ingress_audit_log_path,
        )

    update_id, chat_id = _safe_update_fields(update)
    secret_header = request.headers.get("X-AIOS-TELEGRAM-SECRET")
    expected_secret = os.getenv("AIOS_TELEGRAM_WEBHOOK_SECRET")
    ok_secret, reason = authorize_secret(secret_header, expected_secret)
    if not ok_secret:
        return _deny(
            request=request,
            update_id=update_id,
            chat_id=chat_id,
            reason_code=reason or "DENY_SECRET_INVALID",
            status_code=403,
            ingress_audit_log_path=ingress_audit_log_path,
        )

    normalized = parse_update(update if isinstance(update, dict) else {})
    if normalized is None:
        # Ignore non-text updates with a successful 200 to avoid retries.
        try:
            ingress_audit(
                remote_ip=_remote_ip(request),
                update_id=update_id,
                chat_id=chat_id,
                result="deny",
                reason_code=DENY_NO_MESSAGE,
                audit_log_path=ingress_audit_log_path,
            )
        except RuntimeError:
            return JSONResponse(status_code=403, content={"ok": False, "reason_code": DENY_AUDIT_WRITE_FAILED})
        return JSONResponse(status_code=200, content={"ok": True, "ignored": True})

    allowed = parse_allowed_chat_ids(os.getenv("AIOS_TELEGRAM_ALLOWED_CHAT_IDS"))
    if not is_chat_allowed(normalized["chat_id"], allowed):
        return _deny(
            request=request,
            update_id=normalized.get("update_id"),
            chat_id=normalized.get("chat_id"),
            reason_code=DENY_CHAT_NOT_ALLOWED,
            status_code=403,
            ingress_audit_log_path=ingress_audit_log_path,
        )

    try:
        if replay_detected(
            remote_ip=_remote_ip(request),
            update_id=normalized.get("update_id"),
            chat_id=normalized.get("chat_id"),
            ingress_audit_log_path=ingress_audit_log_path,
        ):
            REPLAYS_BLOCKED += 1
            return JSONResponse(status_code=200, content={"ok": True, "ignored": True})
    except RuntimeError:
        return JSONResponse(status_code=403, content={"ok": False, "reason_code": DENY_AUDIT_WRITE_FAILED})

    try:
        ingress_audit(
            remote_ip=_remote_ip(request),
            update_id=normalized.get("update_id"),
            chat_id=normalized.get("chat_id"),
            result="ok",
            reason_code="OK",
            audit_log_path=ingress_audit_log_path,
        )
    except RuntimeError:
        return JSONResponse(status_code=403, content={"ok": False, "reason_code": DENY_AUDIT_WRITE_FAILED})

    message = normalized.get("text")
    intent = resolve_intent(message if isinstance(message, str) else "")
    if intent is None:
        return _execution_response(
            ok=True,
            executed=False,
            skill_id=None,
            reply="I can help with /send <recipient> <message> or /status.",
            result=None,
            error=None,
        )

    skill_id, payload = intent
    skill_result = run_skill(
        channel_id="telegram",
        user_id=str(normalized["chat_id"]),
        skill_id=skill_id,
        payload=payload,
        policy_path=os.getenv("AIOS_SKILLS_POLICY_PATH", "governance/policy/skills/skills.v0.1.yaml"),
        registry_path=paths["registry_path"],
        config_path=paths["config_path"],
        audit_log_path=os.getenv("AIOS_SKILLS_AUDIT_LOG_PATH", "logs/control/skills.jsonl"),
    )
    if bool(skill_result.get("ok")):
        EVENTS_PROCESSED += 1

    return _execution_response(
        ok=bool(skill_result.get("ok")),
        executed=bool(skill_result.get("ok")),
        skill_id=skill_id,
        reply="Request processed.",
        result=skill_result.get("result"),
        error=skill_result.get("error"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.telegram_webhook_app:app", host="0.0.0.0", port=8000, reload=False)

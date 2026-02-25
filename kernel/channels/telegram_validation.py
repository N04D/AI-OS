"""Startup-time Telegram webhook configuration validation."""

from __future__ import annotations

from typing import Any

import requests


def _error(reason: str) -> RuntimeError:
    return RuntimeError(reason)


def validate_webhook_configuration(
    bot_token: str,
    expected_url: str,
    expected_secret: str,
    timeout_seconds: int = 5,
) -> None:
    if not isinstance(bot_token, str) or not bot_token:
        raise _error("WEBHOOK_VALIDATION_TOKEN_MISSING")
    if not isinstance(expected_url, str) or not expected_url:
        raise _error("WEBHOOK_VALIDATION_EXPECTED_URL_MISSING")
    if not isinstance(expected_secret, str) or not expected_secret:
        raise _error("WEBHOOK_VALIDATION_EXPECTED_SECRET_MISSING")

    endpoint = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    try:
        resp = requests.get(endpoint, timeout=timeout_seconds, verify=True)
    except requests.RequestException as exc:
        raise _error(f"WEBHOOK_VALIDATION_REQUEST_FAILED:{exc}") from exc

    try:
        payload: dict[str, Any] = resp.json()
    except Exception as exc:
        raise _error("WEBHOOK_VALIDATION_BAD_RESPONSE_JSON") from exc

    if payload.get("ok") is not True:
        raise _error("WEBHOOK_VALIDATION_TELEGRAM_OK_FALSE")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise _error("WEBHOOK_VALIDATION_RESULT_MISSING")

    actual_url = result.get("url")
    if actual_url != expected_url:
        raise _error(f"WEBHOOK_URL_MISMATCH:expected={expected_url}:actual={actual_url}")

    actual_secret = result.get("secret_token")
    if actual_secret != expected_secret:
        raise _error("WEBHOOK_SECRET_MISMATCH")

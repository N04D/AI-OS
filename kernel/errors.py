"""Kernel dispatch error helpers."""

from __future__ import annotations

from typing import Any

DISPATCH_INVALID_ARGS = "DISPATCH_INVALID_ARGS"
DISPATCH_RUNNER_REFUSED = "DISPATCH_RUNNER_REFUSED"
DISPATCH_RUNNER_ERROR = "DISPATCH_RUNNER_ERROR"
DISPATCH_INTERNAL_ERROR = "DISPATCH_INTERNAL_ERROR"


def build_error(code: str, message: str, details: list[str] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or [],
    }

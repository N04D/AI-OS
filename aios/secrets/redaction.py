from __future__ import annotations

from typing import Any


def redact(value: Any) -> str:
    """Deterministically redact a potentially sensitive value."""
    if value is None:
        return "***"
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:3]}***{text[-2:]}"

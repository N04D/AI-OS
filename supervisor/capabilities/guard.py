from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from supervisor.autonomy_capabilities import _load_denylist
from supervisor.autonomy_capabilities import load_capability_ledger

DEFAULT_CAPABILITY_LEDGER_PATH = Path("state/supervisor_capabilities.json")
DEFAULT_CAPABILITY_DENYLIST_PATH = Path("state/supervisor_capability_denies.json")
REQUIRED_SCHEDULER_GUARDED_SKILL_RUN = "scheduler_guarded_skill_run"


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    utc_value = parsed.astimezone(UTC)
    if utc_value.utcoffset() != UTC.utcoffset(utc_value):
        raise ValueError("timestamp must be UTC")
    return utc_value


def check_capability(
    capability: str,
    *,
    now_utc: datetime | None = None,
    ledger_path: Path = DEFAULT_CAPABILITY_LEDGER_PATH,
    denylist_path: Path = DEFAULT_CAPABILITY_DENYLIST_PATH,
) -> dict[str, Any]:
    safe_now = now_utc.astimezone(UTC) if isinstance(now_utc, datetime) else datetime.now(UTC)

    if capability in _load_denylist(denylist_path):
        return {"allow": False, "reason_code": "DENY_CAPABILITY_EMERGENCY"}

    ledger = load_capability_ledger(ledger_path)
    entry = ledger.get(capability)
    if not isinstance(entry, dict):
        return {"allow": False, "reason_code": "DENY_CAPABILITY_MISSING"}

    if not bool(entry.get("granted", False)):
        return {"allow": False, "reason_code": "DENY_CAPABILITY_MISSING"}

    expires_at = entry.get("expires_at")
    if isinstance(expires_at, str) and expires_at:
        try:
            expires_utc = _parse_utc(expires_at)
        except ValueError:
            return {"allow": False, "reason_code": "DENY_CAPABILITY_EXPIRED"}
        if expires_utc <= safe_now:
            return {"allow": False, "reason_code": "DENY_CAPABILITY_EXPIRED"}

    return {"allow": True, "reason_code": None}

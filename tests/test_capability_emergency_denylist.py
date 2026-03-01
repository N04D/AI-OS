from __future__ import annotations

import json
from pathlib import Path

from supervisor.autonomy_capabilities import evaluate_capability_access


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_emergency_denylist_blocks_even_granted_capability(tmp_path) -> None:
    ledger_path = tmp_path / "state" / "supervisor_capabilities.json"
    denylist_path = tmp_path / "state" / "supervisor_capability_denies.json"

    _write_json(ledger_path, {"high_risk_pr_merge": True})

    allowed = evaluate_capability_access(
        "high_risk_pr_merge",
        ledger_path=ledger_path,
        denylist_path=denylist_path,
    )
    assert allowed == {"allow": True, "reason_code": None}

    _write_json(
        denylist_path,
        {
            "deny": ["high_risk_pr_merge"],
            "updated_at": "2026-02-25T00:00:00Z",
        },
    )
    denied = evaluate_capability_access(
        "high_risk_pr_merge",
        ledger_path=ledger_path,
        denylist_path=denylist_path,
    )
    assert denied == {"allow": False, "reason_code": "DENY_CAPABILITY_EMERGENCY"}

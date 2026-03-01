from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime

import pytest

from supervisor.budgets import BudgetStateError
from supervisor.budgets import consume_from_path
from supervisor.budgets import load_budget_state


def test_budget_increments_and_denies(tmp_path) -> None:
    path = tmp_path / "state" / "budgets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "v0.1",
                "timezone": "UTC",
                "budgets": {
                    "scheduler_guarded_skill_run": {
                        "window": "daily",
                        "limit": 20,
                        "used": 0,
                        "window_start_utc": None,
                    },
                    "low_risk_pr_merge": {
                        "window": "daily",
                        "limit": 1,
                        "used": 0,
                        "window_start_utc": None,
                    },
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    now_utc = datetime(2026, 2, 25, 12, 0, 0, tzinfo=UTC)
    first = consume_from_path(path, "low_risk_pr_merge", now_utc, cost=1)
    second = consume_from_path(path, "low_risk_pr_merge", now_utc, cost=1)

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["reason_code"] == "DENY_BUDGET_EXCEEDED"


def test_budget_window_rollover_resets_deterministically(tmp_path) -> None:
    path = tmp_path / "state" / "budgets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "v0.1",
                "timezone": "UTC",
                "budgets": {
                    "scheduler_guarded_skill_run": {
                        "window": "daily",
                        "limit": 2,
                        "used": 2,
                        "window_start_utc": "2026-02-24T00:00:00Z",
                    },
                    "low_risk_pr_merge": {
                        "window": "daily",
                        "limit": 5,
                        "used": 3,
                        "window_start_utc": "2026-02-24T00:00:00Z",
                    },
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    now_utc = datetime(2026, 2, 25, 0, 0, 0, tzinfo=UTC)
    result = consume_from_path(path, "scheduler_guarded_skill_run", now_utc, cost=1)

    assert result["ok"] is True
    state = load_budget_state(path)
    assert state["budgets"]["scheduler_guarded_skill_run"]["used"] == 1
    assert state["budgets"]["low_risk_pr_merge"]["used"] == 3


def test_budget_state_invalid_raises_deterministically(tmp_path) -> None:
    path = tmp_path / "state" / "budgets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(BudgetStateError) as exc:
        load_budget_state(path=path)

    assert exc.value.reason_code == "DENY_BUDGET_STATE_INVALID"

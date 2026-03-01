from __future__ import annotations

from datetime import UTC
from datetime import datetime

from supervisor.budgets import DENY_BUDGET_EXCEEDED
from supervisor.budgets import check_and_consume
from supervisor.budgets import default_budget_state


def test_budget_window_initializes_on_first_use() -> None:
    state = default_budget_state()
    now_utc = datetime(2026, 2, 25, 12, 0, 0, tzinfo=UTC)

    ok, updated, reason_code = check_and_consume(state["budgets"], "scheduler_guarded_skill_run", now_utc, cost=1)

    assert ok is True
    assert reason_code is None
    entry = updated["scheduler_guarded_skill_run"]
    assert entry["used"] == 1
    assert entry["window_start_utc"] == "2026-02-25T00:00:00Z"


def test_budget_rollover_resets_at_utc_midnight() -> None:
    state = default_budget_state()
    state["budgets"]["scheduler_guarded_skill_run"]["used"] = 19
    state["budgets"]["scheduler_guarded_skill_run"]["window_start_utc"] = "2026-02-24T00:00:00Z"
    now_utc = datetime(2026, 2, 25, 0, 0, 0, tzinfo=UTC)

    ok, updated, reason_code = check_and_consume(state["budgets"], "scheduler_guarded_skill_run", now_utc, cost=1)

    assert ok is True
    assert reason_code is None
    entry = updated["scheduler_guarded_skill_run"]
    assert entry["used"] == 1
    assert entry["window_start_utc"] == "2026-02-25T00:00:00Z"


def test_budget_consume_increments_used() -> None:
    state = default_budget_state()
    now_utc = datetime(2026, 2, 25, 12, 0, 0, tzinfo=UTC)

    first, budgets_after_first, _ = check_and_consume(state["budgets"], "low_risk_pr_merge", now_utc, cost=1)
    second, budgets_after_second, _ = check_and_consume(budgets_after_first, "low_risk_pr_merge", now_utc, cost=1)

    assert first is True
    assert second is True
    assert budgets_after_second["low_risk_pr_merge"]["used"] == 2


def test_budget_exceed_returns_deny_code() -> None:
    state = default_budget_state()
    state["budgets"]["low_risk_pr_merge"]["limit"] = 1
    state["budgets"]["low_risk_pr_merge"]["used"] = 1
    state["budgets"]["low_risk_pr_merge"]["window_start_utc"] = "2026-02-25T00:00:00Z"
    now_utc = datetime(2026, 2, 25, 12, 0, 0, tzinfo=UTC)

    ok, updated, reason_code = check_and_consume(state["budgets"], "low_risk_pr_merge", now_utc, cost=1)

    assert ok is False
    assert reason_code == DENY_BUDGET_EXCEEDED
    assert updated["low_risk_pr_merge"]["used"] == 1

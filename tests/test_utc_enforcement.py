from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from supervisor.budgets import BudgetStateError
from supervisor.budgets import check_and_consume
from supervisor.budgets import default_budget_state
from supervisor.scheduler.config import SchedulerError
from supervisor.scheduler.config import parse_utc_iso8601


def test_budget_rejects_non_utc_now() -> None:
    state = default_budget_state()
    non_utc = datetime(2026, 2, 27, 12, 0, 0, tzinfo=timezone(timedelta(hours=1)))

    with pytest.raises(BudgetStateError) as exc:
        check_and_consume(state["budgets"], "low_risk_pr_merge", non_utc, cost=1)

    assert exc.value.reason_code == "DENY_BUDGET_STATE_INVALID"
    assert "must be UTC" in str(exc.value)


def test_scheduler_parse_rejects_non_utc_offset() -> None:
    with pytest.raises(SchedulerError) as exc:
        parse_utc_iso8601("2026-02-27T12:00:00+01:00", "DENY_SCHEDULER_TIME_INVALID")

    assert exc.value.reason_code == "DENY_SCHEDULER_TIME_INVALID"
    assert "must be UTC" in str(exc.value)

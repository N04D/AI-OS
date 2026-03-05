from __future__ import annotations

from dataclasses import dataclass
import threading

from .budget_sink import BudgetSink
from .context import SecretAccessContext
from .types import SecretKey


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    mode: str
    classification: str
    cost: int
    spent: int
    limit: int
    reason_code: str | None = None


class BudgetGate:
    def __init__(
        self,
        *,
        mode: str = "off",
        sink: BudgetSink | None = None,
        limits_by_classification: dict[str, int] | None = None,
    ) -> None:
        if mode not in {"off", "observe", "enforce"}:
            raise ValueError("budget mode must be one of: off, observe, enforce")
        self.mode = mode
        self._sink = sink
        self._limits = limits_by_classification or {
            "low": 500,
            "standard": 300,
            "elevated": 150,
        }
        self._spent: dict[tuple[str, str, str], int] = {}
        self._lock = threading.RLock()

    def evaluate_and_charge(self, *, key: SecretKey, context: SecretAccessContext, operation: str) -> BudgetDecision:
        classification = context.trust_level
        agent_id = context.agent_id
        epoch_id = context.epoch_id
        quota_key = (classification, agent_id, epoch_id)
        limit = int(self._limits.get(classification, 0))

        if self.mode == "off":
            return BudgetDecision(
                allowed=True,
                mode=self.mode,
                classification=classification,
                cost=0,
                spent=self._spent.get(quota_key, 0),
                limit=limit,
            )

        if self._sink is None:
            raise RuntimeError("budget sink is required for observe/enforce modes")

        event = self._sink.charge(key=key, context=context, operation=operation)
        cost = int(event.get("cost", 0))
        with self._lock:
            spent = int(self._spent.get(quota_key, 0))
            projected = spent + cost
            if self.mode == "enforce" and projected > limit:
                return BudgetDecision(
                    allowed=False,
                    mode=self.mode,
                    classification=classification,
                    cost=cost,
                    spent=spent,
                    limit=limit,
                    reason_code="BUDGET_EXCEEDED",
                )
            self._spent[quota_key] = projected
            return BudgetDecision(
                allowed=True,
                mode=self.mode,
                classification=classification,
                cost=cost,
                spent=projected,
                limit=limit,
            )

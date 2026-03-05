from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
from typing import Protocol

from .context import SecretAccessContext
from .types import SecretKey


class BudgetSink(Protocol):
    def charge(self, *, key: SecretKey, context: SecretAccessContext, operation: str) -> dict[str, object]:
        ...


@dataclass
class BudgetChargeSink:
    path: Path
    cost_by_classification: dict[str, int] | None = None

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        os.chmod(self.path, 0o600)
        if self.cost_by_classification is None:
            self.cost_by_classification = {
                "low": 1,
                "standard": 2,
                "elevated": 5,
            }

    def charge(self, *, key: SecretKey, context: SecretAccessContext, operation: str) -> dict[str, object]:
        assert self.cost_by_classification is not None
        cost = int(self.cost_by_classification.get(context.trust_level, 0))
        event = {
            "event_type": "secret.budget.charge",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "user": getpass.getuser(),
            "context": context.context_id,
            "classification": context.trust_level,
            "operation": operation,
            "key": key.as_str(),
            "cost": cost,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable

from .types import AccessDenied


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    classification: str
    bucket: str
    count: int
    limit: int
    window_start_epoch: int
    anomaly: bool


class FixedWindowRateLimiter:
    def __init__(
        self,
        *,
        window_seconds: int = 60,
        limits_by_classification: dict[str, int] | None = None,
        anomaly_multiplier: float = 2.0,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        self.window_seconds = int(window_seconds)
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.limits_by_classification = limits_by_classification or {
            "low": 120,
            "standard": 60,
            "elevated": 30,
        }
        self.anomaly_multiplier = float(anomaly_multiplier)
        self.time_source = time_source or time.time
        self._counters: dict[tuple[str, str, int], int] = {}

    def _window_start(self, now_epoch: int) -> int:
        return now_epoch - (now_epoch % self.window_seconds)

    def check_and_increment(self, *, classification: str, bucket: str) -> RateLimitDecision:
        limit = int(self.limits_by_classification.get(classification, 0))
        if limit <= 0:
            raise AccessDenied(f"No rate limit classification configured for '{classification}'")

        now_epoch = int(self.time_source())
        start = self._window_start(now_epoch)
        key = (classification, bucket, start)
        new_count = self._counters.get(key, 0) + 1
        self._counters[key] = new_count

        anomaly_threshold = max(limit + 1, int(math.ceil(limit * self.anomaly_multiplier)))
        anomaly = new_count >= anomaly_threshold
        allowed = new_count <= limit
        return RateLimitDecision(
            allowed=allowed,
            classification=classification,
            bucket=bucket,
            count=new_count,
            limit=limit,
            window_start_epoch=start,
            anomaly=anomaly,
        )

"""In-memory replay cache for ingress update IDs."""

from __future__ import annotations

import time
from collections import OrderedDict


class ReplayCache:
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 600):
        self.max_size = int(max_size)
        self.ttl_seconds = int(ttl_seconds)
        self._seen: OrderedDict[int, float] = OrderedDict()

    def _evict_expired(self, now: float) -> None:
        while self._seen:
            oldest_update_id, oldest_ts = next(iter(self._seen.items()))
            if (now - oldest_ts) <= self.ttl_seconds:
                break
            self._seen.pop(oldest_update_id, None)

    def _evict_oversize(self) -> None:
        while len(self._seen) > self.max_size:
            self._seen.popitem(last=False)

    def seen(self, update_id: int) -> bool:
        if not isinstance(update_id, int):
            return True

        now = time.monotonic()
        self._evict_expired(now)

        ts = self._seen.get(update_id)
        if ts is not None:
            if (now - ts) <= self.ttl_seconds:
                return True
            self._seen.pop(update_id, None)

        self._seen[update_id] = now
        self._evict_oversize()
        return False

from __future__ import annotations

import json
import threading
from pathlib import Path


class ContextKillSwitch:
    def __init__(self, *, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"version": "v0.1", "suspended_contexts": []}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"version": "v0.1", "suspended_contexts": []}
        contexts = raw.get("suspended_contexts")
        if not isinstance(contexts, list):
            contexts = []
        normalized = sorted({str(item) for item in contexts if str(item).strip()})
        return {"version": "v0.1", "suspended_contexts": normalized}

    def _save(self, payload: dict[str, object]) -> None:
        self.path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    def is_suspended(self, context_id: str) -> bool:
        with self._lock:
            state = self._load()
            contexts = state.get("suspended_contexts")
            assert isinstance(contexts, list)
            return str(context_id) in {str(item) for item in contexts}

    def suspend(self, context_id: str) -> None:
        with self._lock:
            state = self._load()
            contexts = {str(item) for item in (state.get("suspended_contexts") or [])}
            contexts.add(str(context_id))
            self._save({"version": "v0.1", "suspended_contexts": sorted(contexts)})

    def unlock(self, context_id: str) -> None:
        with self._lock:
            state = self._load()
            contexts = {str(item) for item in (state.get("suspended_contexts") or [])}
            contexts.discard(str(context_id))
            self._save({"version": "v0.1", "suspended_contexts": sorted(contexts)})

    def list_suspended(self) -> list[str]:
        with self._lock:
            state = self._load()
            contexts = state.get("suspended_contexts")
            assert isinstance(contexts, list)
            return [str(item) for item in contexts]

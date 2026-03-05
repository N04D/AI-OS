from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import getpass
from pathlib import Path

from .contracts import SECRETS_EVENT_SCHEMA_VERSION
from .eventbus import EventSink
from .eventbus import SupervisorEventSink
from .redaction import redact


@dataclass
class AuditLogger:
    path: Path
    sink: EventSink | None = None

    def __post_init__(self) -> None:
        if self.sink is None:
            self.sink = SupervisorEventSink(path=self.path)

    def log(
        self,
        *,
        action: str,
        key: str | None,
        backend: str,
        result: str,
        error_code: str | None = None,
        detail: str | None = None,
    ) -> None:
        event = {
            "schema_version": SECRETS_EVENT_SCHEMA_VERSION,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "user": getpass.getuser(),
            "action": action,
            "key": key,
            "backend": backend,
            "result": result,
            "error_code": error_code,
        }
        if detail:
            # Keep sanitized detail out of event payload because schema is frozen.
            _ = redact(detail)
        assert self.sink is not None
        self.sink.emit(event)

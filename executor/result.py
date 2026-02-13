import dataclasses
import time
from typing import Any


def utc_iso8601() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclasses.dataclass
class ExecutorResult:
    status: str
    changed_files: list[str]
    commit_hash: str | None
    tests_passed: bool
    logs: str
    timestamp: str
    stdout: str
    stderr: str
    exit_status: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def validate_required_output(self) -> None:
        required = {
            "status": self.status,
            "changed_files": self.changed_files,
            "tests_passed": self.tests_passed,
            "logs": self.logs,
            "timestamp": self.timestamp,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(f"execution.result.invalid missing={missing}")
        if self.status not in {"success", "failure"}:
            raise ValueError("execution.result.invalid status must be success|failure")
        if not isinstance(self.changed_files, list):
            raise ValueError("execution.result.invalid changed_files must be a list")

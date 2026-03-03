from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


DENY_ARTIFACT_INVALID = "DENY_ARTIFACT_INVALID"
DENY_ARTIFACT_PATH_ESCAPE = "DENY_ARTIFACT_PATH_ESCAPE"
DENY_SECRET_PERSISTENCE = "DENY_SECRET_PERSISTENCE"
DENY_ARTIFACT_WRITE_FAILED = "DENY_ARTIFACT_WRITE_FAILED"

DEFAULT_AGENT_IO_ROOT = Path("runtime/agent_io")
ALLOWED_CHANNELS = {"inbox", "outbox", "audit"}
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_SENSITIVE_KEY_TOKENS = (
    "token",
    "secret",
    "password",
    "authorization",
    "api_key",
    "private_key",
    "bearer",
)


class AgentIOError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _artifact_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _contains_sensitive_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).strip().lower()
            if any(token in key_text for token in _SENSITIVE_KEY_TOKENS):
                if nested is not None and str(nested).strip() != "":
                    return True
            if _contains_sensitive_keys(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive_keys(item) for item in value)
    return False


class ArtifactWriter:
    def __init__(self, *, repo_root: Path, io_root: Path = DEFAULT_AGENT_IO_ROOT) -> None:
        self.repo_root = Path(repo_root)
        self.io_root = self.repo_root / io_root
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        try:
            for channel in sorted(ALLOWED_CHANNELS):
                (self.io_root / channel).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise AgentIOError(DENY_ARTIFACT_WRITE_FAILED, f"failed to initialize directories: {exc}") from exc

    def _validate_ids(self, *, epoch: str, agent: str) -> None:
        if not isinstance(epoch, str) or not _SAFE_ID_RE.fullmatch(epoch):
            raise AgentIOError(DENY_ARTIFACT_INVALID, "epoch must match [A-Za-z0-9._:-]+")
        if not isinstance(agent, str) or not _SAFE_ID_RE.fullmatch(agent):
            raise AgentIOError(DENY_ARTIFACT_INVALID, "agent must match [A-Za-z0-9._:-]+")

    def _resolve_channel_dir(self, channel: str) -> Path:
        if channel not in ALLOWED_CHANNELS:
            raise AgentIOError(DENY_ARTIFACT_INVALID, f"unsupported channel: {channel}")
        channel_dir = (self.io_root / channel).resolve()
        io_root_resolved = self.io_root.resolve()
        if io_root_resolved not in channel_dir.parents and channel_dir != io_root_resolved:
            raise AgentIOError(DENY_ARTIFACT_PATH_ESCAPE, "channel path escaped io root")
        return channel_dir

    def _resolve_target_path(self, channel: str, filename: str) -> Path:
        channel_dir = self._resolve_channel_dir(channel)
        target = (channel_dir / filename).resolve()
        if channel_dir not in target.parents:
            raise AgentIOError(DENY_ARTIFACT_PATH_ESCAPE, f"target escapes channel directory: {filename}")
        return target

    def write(self, *, channel: str, epoch: str, agent: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_ids(epoch=epoch, agent=agent)
        if not isinstance(payload, dict):
            raise AgentIOError(DENY_ARTIFACT_INVALID, "payload must be a JSON object")
        if _contains_sensitive_keys(payload):
            raise AgentIOError(DENY_SECRET_PERSISTENCE, "payload contains sensitive key/value pairs")

        digest = _artifact_hash(payload)
        filename = f"{epoch}__{agent}__{digest}.json"
        target = self._resolve_target_path(channel, filename)
        text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                existing = target.read_text(encoding="utf-8")
                if existing != text:
                    raise AgentIOError(
                        DENY_ARTIFACT_WRITE_FAILED,
                        f"detected non-idempotent artifact collision at {target}",
                    )
            else:
                target.write_text(text, encoding="utf-8")
        except AgentIOError:
            raise
        except Exception as exc:
            raise AgentIOError(DENY_ARTIFACT_WRITE_FAILED, f"artifact write failed: {exc}") from exc

        return {
            "status": "ok",
            "channel": channel,
            "artifact_path": str(target.relative_to(self.repo_root)),
            "sha256": digest,
        }

    def write_named(self, *, channel: str, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Supports explicit filenames when needed; path safety still enforced.
        """
        if not isinstance(filename, str) or not filename.strip():
            raise AgentIOError(DENY_ARTIFACT_INVALID, "filename is required")
        if not isinstance(payload, dict):
            raise AgentIOError(DENY_ARTIFACT_INVALID, "payload must be a JSON object")
        if _contains_sensitive_keys(payload):
            raise AgentIOError(DENY_SECRET_PERSISTENCE, "payload contains sensitive key/value pairs")

        target = self._resolve_target_path(channel, filename.strip())
        text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        digest = _artifact_hash(payload)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_text(encoding="utf-8") != text:
                    raise AgentIOError(DENY_ARTIFACT_WRITE_FAILED, "existing artifact content mismatch")
            else:
                target.write_text(text, encoding="utf-8")
        except AgentIOError:
            raise
        except Exception as exc:
            raise AgentIOError(DENY_ARTIFACT_WRITE_FAILED, f"artifact write failed: {exc}") from exc

        return {
            "status": "ok",
            "channel": channel,
            "artifact_path": str(target.relative_to(self.repo_root)),
            "sha256": digest,
        }

"""Deterministic audit artifact sink helpers (append-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from executor.secure_execution_layer.audit_event_taxonomy import (
    AuditEvent,
    event_fingerprint,
)
from executor.secure_execution_layer.canonical_hash import canon_json_bytes_v1
from executor.secure_execution_layer.execution_permit_validator import KillSwitchError
from executor.secure_execution_layer.replay_verifier import (
    VerificationResult,
    verify_audit_chain,
)


def build_audit_artifact_path(stream_id: str, sequence: int) -> str:
    if not isinstance(stream_id, str) or not stream_id:
        raise ValueError("secure_layer.audit.invalid stream_id")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise ValueError("secure_layer.audit.invalid sequence")
    return f"audit/streams/{stream_id}/{sequence}.audit.json"


def build_audit_artifact_bytes(event: AuditEvent, *, written_by: str = "supervisor") -> bytes:
    if not isinstance(written_by, str) or not written_by:
        raise ValueError("secure_layer.audit.invalid written_by")
    event_payload = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "policy_hash": event.policy_hash,
        "request_fingerprint": event.request_fingerprint,
        "sequence": event.sequence,
        "stream_id": event.stream_id,
        "prev_event_hash": event.prev_event_hash,
        "payload": event.payload,
    }
    artifact = {
        "event": event_payload,
        "event_hash": event_fingerprint(event),
        "written_by": written_by,
        "version": 1,
    }
    return canon_json_bytes_v1(artifact)


class AuditArtifactWriter(Protocol):
    def write_event(self, event: AuditEvent) -> str: ...


@dataclass(frozen=True)
class GitWorktreeAuditWriter:
    repo_root: str

    def write_event(self, event: AuditEvent) -> str:
        rel_path = build_audit_artifact_path(event.stream_id, event.sequence)
        full_path = Path(self.repo_root) / rel_path
        if full_path.exists():
            raise KillSwitchError("secure_layer.killswitch.audit_append_violation")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(build_audit_artifact_bytes(event))
        return rel_path


def load_audit_stream_from_repo(repo_root: str, stream_id: str) -> list[tuple[AuditEvent, str]]:
    if not isinstance(stream_id, str) or not stream_id:
        raise ValueError("secure_layer.replay.invalid stream_id")
    stream_dir = Path(repo_root) / "audit" / "streams" / stream_id
    if not stream_dir.exists() or not stream_dir.is_dir():
        raise ValueError("secure_layer.replay.invalid stream_missing")

    entries = []
    for child in stream_dir.iterdir():
        if child.is_file() and child.name.endswith(".audit.json"):
            seq_str = child.name[: -len(".audit.json")]
            if not seq_str.isdigit():
                raise ValueError("secure_layer.replay.invalid sequence_file")
            entries.append((int(seq_str), child))

    if not entries:
        return []

    entries.sort(key=lambda item: item[0])
    expected = 0
    loaded: list[tuple[AuditEvent, str]] = []
    for sequence, path in entries:
        if sequence != expected:
            raise ValueError("secure_layer.replay.invalid missing_sequence")
        expected += 1
        data = json.loads(path.read_text(encoding="utf-8"))
        event_data = data.get("event")
        if not isinstance(event_data, Mapping):
            raise ValueError("secure_layer.replay.invalid event_payload")
        event = AuditEvent(
            event_id=str(event_data["event_id"]),
            event_type=event_data["event_type"],
            policy_hash=str(event_data["policy_hash"]),
            request_fingerprint=str(event_data["request_fingerprint"]),
            sequence=int(event_data["sequence"]),
            stream_id=str(event_data["stream_id"]),
            prev_event_hash=event_data.get("prev_event_hash"),
            payload=event_data["payload"],
        )
        stored_hash = str(data.get("event_hash", ""))
        computed_hash = event_fingerprint(event)
        if stored_hash != computed_hash:
            raise ValueError("secure_layer.replay.invalid event_hash_mismatch")
        loaded.append((event, stored_hash))
    return loaded


def verify_audit_stream_from_repo(repo_root: str, stream_id: str) -> VerificationResult:
    loaded = load_audit_stream_from_repo(repo_root, stream_id)
    events = [item[0] for item in loaded]
    return verify_audit_chain(events, stream_id)

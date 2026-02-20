"""Deterministic audit event taxonomy scaffolding.

Pure helpers only: no I/O, no clock access, no runtime sink coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

AuditEventType = Literal[
    "policy.evaluated",
    "tool.exec.requested",
    "tool.exec.allowed",
    "tool.exec.blocked",
    "tool.exec.warned",
    "tool.exec.reviewed",
    "net.egress.requested",
    "net.egress.allowed",
    "net.egress.blocked",
    "net.egress.warned",
    "net.egress.reviewed",
    "secret.use.requested",
    "secret.use.allowed",
    "secret.use.blocked",
    "secret.use.warned",
    "secret.use.reviewed",
    "review.paused",
    "review.resolved",
]


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    policy_hash: str
    prev_event_id: str | None = None
    sequence: int | None = None
    stream_hash: str | None = None


def validate_audit_event(event: AuditEvent) -> None:
    if not event.event_id:
        raise ValueError("secure_layer.audit.invalid event_id")
    if not event.policy_hash:
        raise ValueError("secure_layer.audit.invalid policy_hash")

    has_hash_chain = bool(event.prev_event_id)
    has_sequence_chain = event.sequence is not None and bool(event.stream_hash)
    if not (has_hash_chain or has_sequence_chain):
        raise ValueError("secure_layer.audit.invalid requires prev_event_id or sequence+stream_hash")

    if event.sequence is not None and event.sequence < 0:
        raise ValueError("secure_layer.audit.invalid sequence")


def validate_event_stream(events: list[AuditEvent]) -> None:
    if not events:
        return

    for event in events:
        validate_audit_event(event)

    # Enforce one deterministic chain model per stream.
    uses_hash_chain = all(event.prev_event_id is not None for event in events)
    uses_sequence_chain = all(
        event.sequence is not None and event.stream_hash is not None for event in events
    )
    if not (uses_hash_chain or uses_sequence_chain):
        raise ValueError("secure_layer.audit.invalid mixed chain models")

    if uses_sequence_chain:
        expected_sequence = 0
        first_stream_hash = events[0].stream_hash
        for event in events:
            if event.sequence != expected_sequence:
                raise ValueError("secure_layer.audit.invalid non_contiguous_sequence")
            if event.stream_hash != first_stream_hash:
                raise ValueError("secure_layer.audit.invalid stream_hash_mismatch")
            expected_sequence += 1


def event_fingerprint(event: AuditEvent) -> str:
    payload = "|".join(
        [
            event.event_id,
            event.event_type,
            event.policy_hash,
            event.prev_event_id or "",
            str(event.sequence) if event.sequence is not None else "",
            event.stream_hash or "",
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()

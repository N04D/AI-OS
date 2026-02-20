"""Deterministic audit event taxonomy scaffolding.

Pure helpers only: no I/O, no clock access, no runtime sink coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from executor.secure_execution_layer.canonical_hash import (
    build_audit_event_body_input,
    build_audit_event_identity_input,
    domain_hash,
)
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
    request_fingerprint: str
    sequence: int
    stream_id: str
    prev_event_hash: str | None
    payload: Mapping[str, Any]


def validate_audit_event(event: AuditEvent) -> None:
    if not event.event_id:
        raise ValueError("secure_layer.audit.invalid event_id")
    if not event.policy_hash:
        raise ValueError("secure_layer.audit.invalid policy_hash")
    if not event.request_fingerprint:
        raise ValueError("secure_layer.audit.invalid request_fingerprint")
    if not event.stream_id:
        raise ValueError("secure_layer.audit.invalid stream_id")
    if event.sequence < 0:
        raise ValueError("secure_layer.audit.invalid sequence")
    if not isinstance(event.payload, Mapping):
        raise ValueError("secure_layer.audit.invalid payload")


def validate_event_stream(events: list[AuditEvent]) -> None:
    if not events:
        return

    first_stream_id = events[0].stream_id
    for event in events:
        validate_audit_event(event)
        if event.stream_id != first_stream_id:
            raise ValueError("secure_layer.audit.invalid stream_id_mismatch")

    expected_sequence = 0
    previous_hash: str | None = None
    for event in events:
        if event.sequence != expected_sequence:
            raise ValueError("secure_layer.audit.invalid non_contiguous_sequence")
        expected_prev = previous_hash or ""
        if (event.prev_event_hash or "") != expected_prev:
            raise ValueError("secure_layer.audit.invalid prev_event_hash_mismatch")
        previous_hash = event_fingerprint(event)
        expected_sequence += 1


def event_fingerprint(event: AuditEvent) -> str:
    identity_input = build_audit_event_identity_input(
        event_id=event.event_id,
        event_type=event.event_type,
        policy_hash=event.policy_hash,
        request_fingerprint=event.request_fingerprint,
        sequence=event.sequence,
        stream_id=event.stream_id,
        prev_event_hash=event.prev_event_hash,
    )
    body_input = build_audit_event_body_input(payload=event.payload)
    return domain_hash(
        "secure_execution_layer.audit_event.v1",
        {"identity": identity_input, "body": body_input},
    )

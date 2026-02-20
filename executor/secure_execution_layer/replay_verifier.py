"""Pure replay verification helpers for secure execution layer audit streams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from executor.secure_execution_layer.audit_event_taxonomy import AuditEvent
from executor.secure_execution_layer.canonical_hash import (
    build_audit_event_body_input,
    build_audit_event_identity_input,
    build_review_decision_input,
    build_review_id_input,
    domain_hash,
)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    error: str | None = None
    failed_index: int | None = None


def verify_audit_chain(events: list[AuditEvent], stream_id: str) -> VerificationResult:
    if not stream_id:
        return VerificationResult(ok=False, error="secure_layer.replay.invalid stream_id")
    if not events:
        return VerificationResult(ok=True)

    previous_hash: str | None = None
    expected_sequence = 0

    for index, event in enumerate(events):
        if event.stream_id != stream_id:
            return VerificationResult(ok=False, error="secure_layer.replay.invalid stream_id_mismatch", failed_index=index)
        if not event.policy_hash:
            return VerificationResult(ok=False, error="secure_layer.replay.invalid policy_hash", failed_index=index)
        if not event.request_fingerprint:
            return VerificationResult(ok=False, error="secure_layer.replay.invalid request_fingerprint", failed_index=index)
        if event.sequence != expected_sequence:
            return VerificationResult(ok=False, error="secure_layer.replay.invalid sequence", failed_index=index)

        expected_prev = previous_hash or ""
        if (event.prev_event_hash or "") != expected_prev:
            return VerificationResult(ok=False, error="secure_layer.replay.invalid prev_event_hash", failed_index=index)

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
        event_hash = domain_hash(
            "secure_execution_layer.audit_event.v1",
            {"identity": identity_input, "body": body_input},
        )

        previous_hash = event_hash
        expected_sequence += 1

    return VerificationResult(ok=True)


def verify_review_resume(
    policy_hash: str,
    request_fingerprint: str,
    review_artifact: Mapping[str, Any] | None,
) -> bool:
    if review_artifact is None:
        return False

    try:
        review_id = str(review_artifact["review_id"])
        artifact_policy_hash = str(review_artifact["policy_hash"])
        artifact_request_fingerprint = str(review_artifact["request_fingerprint"])
        decision = str(review_artifact["decision"])
        decided_by = str(review_artifact["decided_by"])
        signature_ref = str(review_artifact["signature_ref"])
    except KeyError:
        return False

    expected_review_id = domain_hash(
        "secure_execution_layer.review_id.v1",
        build_review_id_input(
            policy_hash=policy_hash,
            request_fingerprint=request_fingerprint,
        ),
    )
    if review_id != expected_review_id:
        return False
    if artifact_policy_hash != policy_hash:
        return False
    if artifact_request_fingerprint != request_fingerprint:
        return False

    try:
        build_review_decision_input(
            review_id=review_id,
            policy_hash=artifact_policy_hash,
            request_fingerprint=artifact_request_fingerprint,
            decision=decision,
            decided_by=decided_by,
            signature_ref=signature_ref,
        )
    except ValueError:
        return False

    return decision in ("allow", "block")

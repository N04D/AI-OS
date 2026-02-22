"""Pure review ledger resolution scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

LedgerResolution = Literal["allow", "block", "unresolved"]


@dataclass(frozen=True)
class ReviewArtifact:
    review_id: str
    policy_hash: str
    request_fingerprint: str
    decision: Literal["allow", "block"]


class ReviewLedgerResolver(Protocol):
    """Pure interface. Implementations must not perform hidden state mutations."""

    def resolve(
        self,
        review_id: str,
        request_fingerprint: str,
        policy_hash: str,
    ) -> LedgerResolution: ...


def resolve_review_artifact(
    artifact: ReviewArtifact | None,
    *,
    review_id: str,
    request_fingerprint: str,
    policy_hash: str,
) -> LedgerResolution:
    """Deterministic artifact validation for review resume.

    Returns unresolved if artifact is missing or does not match review
    identity, policy hash, or request fingerprint.
    """

    if artifact is None:
        return "unresolved"
    if artifact.review_id != review_id:
        return "unresolved"
    if artifact.policy_hash != policy_hash:
        return "unresolved"
    if artifact.request_fingerprint != request_fingerprint:
        return "unresolved"
    return artifact.decision


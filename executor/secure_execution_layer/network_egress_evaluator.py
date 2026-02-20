"""Pure network egress evaluation scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

EgressDecision = Literal["allow", "block", "review"]
DnsReplayMode = Literal["pinned_ips", "resolution_snapshot_hash"]


@dataclass(frozen=True)
class EgressRequest:
    host: str
    path: str
    method: str


@dataclass(frozen=True)
class ResolutionSnapshot:
    dns_replay_mode: DnsReplayMode
    resolved_ips: tuple[str, ...] = ()
    resolution_snapshot_hash: str | None = None


class NetworkEgressEvaluator(Protocol):
    """Pure interface. Implementations require deterministic resolution input."""

    def evaluate(
        self,
        request: EgressRequest,
        policy_document: dict,
        resolution: ResolutionSnapshot,
    ) -> EgressDecision: ...


def validate_network_egress_initialization(
    *,
    interpretation_authority: str,
    conflict_resolution: dict | None,
    dns_replay_mode: str | None,
) -> None:
    if interpretation_authority != "supervisor":
        raise ValueError("secure_layer.init.invalid interpretation_authority must be supervisor")
    if not conflict_resolution:
        raise ValueError("secure_layer.init.invalid conflict_resolution required")
    if dns_replay_mode not in ("pinned_ips", "resolution_snapshot_hash"):
        raise ValueError("secure_layer.init.invalid dns_replay_mode required")


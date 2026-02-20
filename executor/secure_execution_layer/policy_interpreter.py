"""Pure deterministic policy interpretation scaffolding.

No I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ConflictResolutionMode = Literal["deny_wins", "most_specific", "explicit_priority"]
TieBreaker = Literal["stable_order"]
StableOrderMode = Literal["lexical_rule_id", "order_index"]
DecisionEffect = Literal["allow", "warn", "review", "block"]


@dataclass(frozen=True)
class PolicyInterpretationConfig:
    interpretation_authority: str
    conflict_resolution_mode: ConflictResolutionMode
    tie_breaker: TieBreaker
    stable_order_mode: StableOrderMode


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    effect: DecisionEffect
    specificity: int = 0
    priority: int = 0
    order_index: int = 0


@dataclass(frozen=True)
class Decision:
    effect: DecisionEffect
    selected_rule_id: str | None
    reason: str


class PolicyInterpreter(Protocol):
    """Pure interface. Implementations must remain deterministic and side-effect free."""

    def interpret(
        self,
        policy_document: dict,
        request_context: dict,
        config: PolicyInterpretationConfig,
    ) -> Decision: ...


def validate_policy_interpretation_config(config: PolicyInterpretationConfig) -> None:
    if config.interpretation_authority != "supervisor":
        raise ValueError("secure_layer.init.invalid interpretation_authority must be supervisor")
    if config.conflict_resolution_mode not in ("deny_wins", "most_specific", "explicit_priority"):
        raise ValueError("secure_layer.init.invalid missing or invalid conflict_resolution_mode")
    if config.tie_breaker != "stable_order":
        raise ValueError("secure_layer.init.invalid tie_breaker must be stable_order")
    if config.stable_order_mode not in ("lexical_rule_id", "order_index"):
        raise ValueError("secure_layer.init.invalid stable_order_mode")


def validate_secure_layer_initialization(
    *,
    config: PolicyInterpretationConfig,
    emitted_severities: list[DecisionEffect],
    review_ledger_resolver: object | None,
) -> None:
    """Initialization guardrails from v0.2-delta.

    Fails when:
    - interpretation_authority is not supervisor
    - conflict_resolution is missing/invalid
    - review severity is used without a ledger resolver
    """

    validate_policy_interpretation_config(config)
    if "review" in emitted_severities and review_ledger_resolver is None:
        raise ValueError("secure_layer.init.invalid review severity requires ledger resolver")


def resolve_overlapping_rules(
    matches: list[RuleMatch],
    config: PolicyInterpretationConfig,
) -> Decision:
    """Deterministically resolve overlapping rules.

    This is a minimal, pure reference resolver for scaffolding and tests only.
    """

    validate_policy_interpretation_config(config)
    if not matches:
        return Decision(effect="block", selected_rule_id=None, reason="no_matching_rule")

    if config.conflict_resolution_mode == "deny_wins":
        blocked = _first_effect(matches, "block", config)
        if blocked is not None:
            return Decision(effect="block", selected_rule_id=blocked.rule_id, reason="deny_wins")
        selected = _stable_pick(matches, config)
        return Decision(effect=selected.effect, selected_rule_id=selected.rule_id, reason="deny_wins_fallback")

    if config.conflict_resolution_mode == "most_specific":
        max_specificity = max(m.specificity for m in matches)
        candidates = [m for m in matches if m.specificity == max_specificity]
        selected = _stable_pick(candidates, config)
        return Decision(effect=selected.effect, selected_rule_id=selected.rule_id, reason="most_specific")

    # explicit_priority
    max_priority = max(m.priority for m in matches)
    candidates = [m for m in matches if m.priority == max_priority]
    selected = _stable_pick(candidates, config)
    return Decision(effect=selected.effect, selected_rule_id=selected.rule_id, reason="explicit_priority")


def _first_effect(
    matches: list[RuleMatch],
    effect: DecisionEffect,
    config: PolicyInterpretationConfig,
) -> RuleMatch | None:
    candidates = [m for m in matches if m.effect == effect]
    if not candidates:
        return None
    return _stable_pick(candidates, config)


def _stable_pick(matches: list[RuleMatch], config: PolicyInterpretationConfig) -> RuleMatch:
    if config.stable_order_mode == "lexical_rule_id":
        return sorted(matches, key=lambda m: m.rule_id)[0]
    return sorted(matches, key=lambda m: (m.order_index, m.rule_id))[0]


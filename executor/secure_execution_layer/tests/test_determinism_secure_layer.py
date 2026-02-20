from executor.secure_execution_layer.policy_interpreter import (
    PolicyInterpretationConfig,
    RuleMatch,
    resolve_overlapping_rules,
    validate_secure_layer_initialization,
)
from executor.secure_execution_layer.network_egress_evaluator import (
    validate_network_egress_initialization,
)
from executor.secure_execution_layer.review_ledger_resolver import (
    ReviewArtifact,
    resolve_review_artifact,
)
from executor.secure_execution_layer.secret_injection_validator import (
    SecretRef,
    validate_secret_injection,
)


def test_overlapping_rules_explicit_priority_is_deterministic() -> None:
    config = PolicyInterpretationConfig(
        interpretation_authority="supervisor",
        conflict_resolution_mode="explicit_priority",
        tie_breaker="stable_order",
        stable_order_mode="lexical_rule_id",
    )
    matches = [
        RuleMatch(rule_id="z_rule", effect="allow", priority=10, specificity=1),
        RuleMatch(rule_id="a_rule", effect="review", priority=10, specificity=1),
    ]
    decision = resolve_overlapping_rules(matches, config)
    assert decision.effect == "review"
    assert decision.selected_rule_id == "a_rule"


def test_tie_breaker_uses_order_index_when_configured() -> None:
    config = PolicyInterpretationConfig(
        interpretation_authority="supervisor",
        conflict_resolution_mode="most_specific",
        tie_breaker="stable_order",
        stable_order_mode="order_index",
    )
    matches = [
        RuleMatch(rule_id="a", effect="allow", specificity=5, order_index=2),
        RuleMatch(rule_id="b", effect="warn", specificity=5, order_index=1),
    ]
    decision = resolve_overlapping_rules(matches, config)
    assert decision.effect == "warn"
    assert decision.selected_rule_id == "b"


def test_deny_wins_precedence() -> None:
    config = PolicyInterpretationConfig(
        interpretation_authority="supervisor",
        conflict_resolution_mode="deny_wins",
        tie_breaker="stable_order",
        stable_order_mode="lexical_rule_id",
    )
    matches = [
        RuleMatch(rule_id="allow_rule", effect="allow", priority=100),
        RuleMatch(rule_id="block_rule", effect="block", priority=1),
    ]
    decision = resolve_overlapping_rules(matches, config)
    assert decision.effect == "block"
    assert decision.selected_rule_id == "block_rule"


def test_review_cannot_resume_without_matching_ledger_artifact() -> None:
    decision = resolve_review_artifact(
        artifact=None,
        review_id="r-1",
        request_fingerprint="fp-1",
        policy_hash="h-1",
    )
    assert decision == "unresolved"

    wrong_hash = resolve_review_artifact(
        artifact=ReviewArtifact(
            review_id="r-1",
            policy_hash="h-other",
            request_fingerprint="fp-1",
            decision="allow",
        ),
        review_id="r-1",
        request_fingerprint="fp-1",
        policy_hash="h-1",
    )
    assert wrong_hash == "unresolved"

    wrong_fp = resolve_review_artifact(
        artifact=ReviewArtifact(
            review_id="r-1",
            policy_hash="h-1",
            request_fingerprint="fp-other",
            decision="allow",
        ),
        review_id="r-1",
        request_fingerprint="fp-1",
        policy_hash="h-1",
    )
    assert wrong_fp == "unresolved"


def test_guardrail_fails_when_review_emitted_without_resolver() -> None:
    config = PolicyInterpretationConfig(
        interpretation_authority="supervisor",
        conflict_resolution_mode="deny_wins",
        tie_breaker="stable_order",
        stable_order_mode="lexical_rule_id",
    )
    try:
        validate_secure_layer_initialization(
            config=config,
            emitted_severities=["allow", "review"],
            review_ledger_resolver=None,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "requires ledger resolver" in str(exc)


def test_guardrail_fails_when_review_resolver_contract_missing() -> None:
    config = PolicyInterpretationConfig(
        interpretation_authority="supervisor",
        conflict_resolution_mode="deny_wins",
        tie_breaker="stable_order",
        stable_order_mode="lexical_rule_id",
    )
    try:
        validate_secure_layer_initialization(
            config=config,
            emitted_severities=["review"],
            review_ledger_resolver=object(),
        )
        assert False, "Expected TypeError"
    except TypeError as exc:
        assert "ledger resolver contract" in str(exc)


def test_network_egress_init_requires_deterministic_conflict_structure() -> None:
    validate_network_egress_initialization(
        interpretation_authority="supervisor",
        conflict_resolution={
            "mode": "deny_wins",
            "tie_breaker": "stable_order",
            "stable_order_mode": "lexical_rule_id",
        },
        dns_replay_mode="pinned_ips",
    )

    try:
        validate_network_egress_initialization(
            interpretation_authority="supervisor",
            conflict_resolution={"mode": "deny_wins"},
            dns_replay_mode="pinned_ips",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "conflict_resolution.tie_breaker" in str(exc)


def test_secret_validator_requires_expiry_or_rotation() -> None:
    secret_ref = SecretRef(provider="vault", key="service/api-key")
    result = validate_secret_injection(
        secret_ref=secret_ref,
        injection_mode="header",
        disallowed_injection_modes={"query_param", "url_path"},
    )
    assert result == "invalid"

    valid_ref = SecretRef(
        provider="vault",
        key="service/api-key",
        rotation_ttl_seconds=3600,
    )
    valid = validate_secret_injection(
        secret_ref=valid_ref,
        injection_mode="header",
        disallowed_injection_modes={"query_param", "url_path"},
    )
    assert valid == "valid"

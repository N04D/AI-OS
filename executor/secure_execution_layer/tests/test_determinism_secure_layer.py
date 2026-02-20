from executor.secure_execution_layer.policy_interpreter import (
    PolicyInterpretationConfig,
    RuleMatch,
    resolve_overlapping_rules,
    validate_secure_layer_initialization,
)
from executor.secure_execution_layer.network_egress_evaluator import (
    validate_network_egress_initialization,
)
from executor.secure_execution_layer.audit_event_taxonomy import (
    AuditEvent,
    event_fingerprint,
    validate_audit_event,
    validate_event_stream,
)
from executor.secure_execution_layer.canonical_hash import (
    build_audit_event_body_input,
    build_audit_event_identity_input,
    build_review_id_input,
    canon_json_bytes_v1,
    domain_hash,
)
from executor.secure_execution_layer.replay_verifier import (
    verify_audit_chain,
    verify_review_resume,
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


def test_canonical_json_stability_and_key_order() -> None:
    left = {"b": {"y": 2, "x": 1}, "a": "ok"}
    right = {"a": "ok", "b": {"x": 1, "y": 2}}
    assert canon_json_bytes_v1(left) == canon_json_bytes_v1(right)


def test_domain_separation_changes_hash() -> None:
    obj = {"field": "value", "count": 1}
    first = domain_hash("secure_execution_layer.audit_event.v1", obj)
    second = domain_hash("secure_execution_layer.review_id.v1", obj)
    assert first != second


def test_canon_json_rejects_floats() -> None:
    try:
        canon_json_bytes_v1({"latency_ms": 1.5})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "float_forbidden" in str(exc)


def test_event_hash_determinism_and_semantic_change() -> None:
    base = AuditEvent(
        event_id="evt-1",
        event_type="review.paused",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"action": "pause"},
    )
    first = event_fingerprint(base)
    second = event_fingerprint(base)
    assert first == second

    changed = AuditEvent(
        event_id="evt-1",
        event_type="review.paused",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"action": "resume"},
    )
    assert event_fingerprint(changed) != first


def test_audit_event_requires_policy_and_request_and_payload() -> None:
    try:
        validate_audit_event(
            AuditEvent(
                event_id="evt-1",
                event_type="policy.evaluated",
                policy_hash="",
                request_fingerprint="req-1",
                sequence=0,
                stream_id="stream-1",
                prev_event_hash=None,
                payload={"k": "v"},
            )
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "policy_hash" in str(exc)

    try:
        validate_audit_event(
            AuditEvent(
                event_id="evt-1",
                event_type="policy.evaluated",
                policy_hash="hash-1",
                request_fingerprint="",
                sequence=0,
                stream_id="stream-1",
                prev_event_hash=None,
                payload={"k": "v"},
            )
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "request_fingerprint" in str(exc)


def test_chain_integrity_rejects_non_contiguous_sequence_and_prev_hash_mismatch() -> None:
    first = AuditEvent(
        event_id="evt-0",
        event_type="policy.evaluated",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"step": "start"},
    )
    second = AuditEvent(
        event_id="evt-1",
        event_type="tool.exec.requested",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=2,
        stream_id="stream-1",
        prev_event_hash=event_fingerprint(first),
        payload={"tool": "x"},
    )
    non_contiguous = verify_audit_chain([first, second], "stream-1")
    assert non_contiguous.ok is False
    assert non_contiguous.error == "secure_layer.replay.invalid sequence"

    second_bad_prev = AuditEvent(
        event_id="evt-1",
        event_type="tool.exec.requested",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=1,
        stream_id="stream-1",
        prev_event_hash="wrong",
        payload={"tool": "x"},
    )
    wrong_prev = verify_audit_chain([first, second_bad_prev], "stream-1")
    assert wrong_prev.ok is False
    assert wrong_prev.error == "secure_layer.replay.invalid prev_event_hash"


def test_verify_audit_chain_rejects_stream_id_mismatch() -> None:
    first = AuditEvent(
        event_id="evt-0",
        event_type="policy.evaluated",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"step": "start"},
    )
    result = verify_audit_chain([first], "stream-2")
    assert result.ok is False
    assert result.error == "secure_layer.replay.invalid stream_id_mismatch"


def test_verify_audit_chain_rejects_wrong_input_order_without_auto_sort() -> None:
    first = AuditEvent(
        event_id="evt-0",
        event_type="policy.evaluated",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"step": "start"},
    )
    second = AuditEvent(
        event_id="evt-1",
        event_type="tool.exec.requested",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=1,
        stream_id="stream-1",
        prev_event_hash=event_fingerprint(first),
        payload={"tool": "x"},
    )
    out_of_order = verify_audit_chain([second, first], "stream-1")
    assert out_of_order.ok is False
    assert out_of_order.error == "secure_layer.replay.invalid sequence"


def test_audit_event_stream_requires_deterministic_contiguous_sequence() -> None:
    first = AuditEvent(
        event_id="evt-0",
        event_type="policy.evaluated",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"step": "start"},
    )
    second = AuditEvent(
        event_id="evt-1",
        event_type="tool.exec.requested",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=1,
        stream_id="stream-1",
        prev_event_hash=event_fingerprint(first),
        payload={"tool": "x"},
    )
    validate_event_stream([first, second])


def test_review_resume_verification_contract() -> None:
    policy_hash = "policy-h-1"
    request_fingerprint = "req-fp-1"
    review_id = domain_hash(
        "secure_execution_layer.review_id.v1",
        build_review_id_input(
            policy_hash=policy_hash,
            request_fingerprint=request_fingerprint,
        ),
    )

    assert verify_review_resume(policy_hash, request_fingerprint, None) is False

    mismatched_policy = {
        "review_id": review_id,
        "policy_hash": "other",
        "request_fingerprint": request_fingerprint,
        "decision": "allow",
        "decided_by": "actor-1",
        "signature_ref": "sig-1",
    }
    assert verify_review_resume(policy_hash, request_fingerprint, mismatched_policy) is False

    mismatched_fp = {
        "review_id": review_id,
        "policy_hash": policy_hash,
        "request_fingerprint": "other",
        "decision": "allow",
        "decided_by": "actor-1",
        "signature_ref": "sig-1",
    }
    assert verify_review_resume(policy_hash, request_fingerprint, mismatched_fp) is False

    allow_artifact = {
        "review_id": review_id,
        "policy_hash": policy_hash,
        "request_fingerprint": request_fingerprint,
        "decision": "allow",
        "decided_by": "actor-1",
        "signature_ref": "sig-1",
        "timestamp_utc": "2026-02-20T00:00:00Z",
    }
    block_artifact = {
        "review_id": review_id,
        "policy_hash": policy_hash,
        "request_fingerprint": request_fingerprint,
        "decision": "block",
        "decided_by": "actor-1",
        "signature_ref": "sig-2",
    }
    assert verify_review_resume(policy_hash, request_fingerprint, allow_artifact) is True
    assert verify_review_resume(policy_hash, request_fingerprint, block_artifact) is True


def test_identity_and_body_builders_fail_closed() -> None:
    try:
        build_audit_event_identity_input(
            event_id="",
            event_type="policy.evaluated",
            policy_hash="hash-1",
            request_fingerprint="req-1",
            sequence=0,
            stream_id="stream-1",
            prev_event_hash=None,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "event_id" in str(exc)

    try:
        build_audit_event_body_input(payload={"latency_ms": 1.5})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "float_forbidden" in str(exc)


def test_audit_event_fingerprint_is_stable() -> None:
    event = AuditEvent(
        event_id="evt-1",
        event_type="review.paused",
        policy_hash="hash-1",
        request_fingerprint="req-1",
        sequence=0,
        stream_id="stream-1",
        prev_event_hash=None,
        payload={"stage": "pause"},
    )
    first = event_fingerprint(event)
    second = event_fingerprint(event)
    assert first == second

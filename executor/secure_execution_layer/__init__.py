"""Deterministic scaffolding for the Secure Execution Layer.

This package intentionally contains pure interfaces and deterministic helper
functions only. It does not perform I/O, networking, clock access, or any
runtime enforcement side effects.
"""

from executor.secure_execution_layer.network_egress_evaluator import (
    EgressDecision,
    EgressRequest,
    NetworkEgressEvaluator,
    ResolutionSnapshot,
    validate_network_egress_initialization,
)
from executor.secure_execution_layer.canonical_hash import (
    build_audit_event_body_input,
    build_audit_event_identity_input,
    build_policy_hash_input,
    build_request_fingerprint_input,
    build_review_decision_input,
    build_review_id_input,
    canon_json_bytes_v1,
    domain_hash,
)
from executor.secure_execution_layer.audit_event_taxonomy import (
    AuditEvent,
    AuditEventType,
    event_fingerprint,
    validate_audit_event,
    validate_event_stream,
)
from executor.secure_execution_layer.replay_verifier import (
    VerificationResult,
    verify_audit_chain,
    verify_review_resume,
)
from executor.secure_execution_layer.policy_interpreter import (
    ConflictResolutionMode,
    Decision,
    PolicyInterpretationConfig,
    PolicyInterpreter,
    ReviewLedgerResolverProtocol,
    RuleMatch,
    resolve_overlapping_rules,
    validate_policy_interpretation_config,
    validate_secure_layer_initialization,
)
from executor.secure_execution_layer.review_ledger_resolver import (
    LedgerResolution,
    ReviewArtifact,
    ReviewLedgerResolver,
    resolve_review_artifact,
)
from executor.secure_execution_layer.secret_injection_validator import (
    SecretInjectionMode,
    SecretInjectionValidator,
    SecretRef,
    ValidationResult,
    validate_secret_injection,
)

__all__ = [
    "ConflictResolutionMode",
    "Decision",
    "AuditEvent",
    "AuditEventType",
    "VerificationResult",
    "EgressDecision",
    "EgressRequest",
    "LedgerResolution",
    "NetworkEgressEvaluator",
    "PolicyInterpretationConfig",
    "PolicyInterpreter",
    "ReviewLedgerResolverProtocol",
    "ResolutionSnapshot",
    "ReviewArtifact",
    "ReviewLedgerResolver",
    "RuleMatch",
    "SecretInjectionMode",
    "SecretInjectionValidator",
    "SecretRef",
    "ValidationResult",
    "resolve_overlapping_rules",
    "build_audit_event_body_input",
    "build_audit_event_identity_input",
    "build_policy_hash_input",
    "build_request_fingerprint_input",
    "build_review_decision_input",
    "build_review_id_input",
    "canon_json_bytes_v1",
    "domain_hash",
    "event_fingerprint",
    "validate_audit_event",
    "validate_event_stream",
    "verify_audit_chain",
    "verify_review_resume",
    "resolve_review_artifact",
    "validate_network_egress_initialization",
    "validate_policy_interpretation_config",
    "validate_secure_layer_initialization",
    "validate_secret_injection",
]

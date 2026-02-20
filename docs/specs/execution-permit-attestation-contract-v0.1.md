# Execution Permit Attestation Contract v0.1

Status: Experimental
Scope: Specification only (no runtime wiring)

## 1. Purpose and Threat Model

This contract defines a deterministic, stateless execution permit that is issued by the Supervisor and verified by the Executor before any governed capability is exercised.

Primary threats addressed:
- Shadow autonomy (execution without governed attestation)
- Bypass of PR-gated governance and policy replay controls
- Non-replayable runtime decisions that cannot be reconstructed from Git + deterministic inputs

Security objective:
Every execution attempt must be bound to:
- `policy_hash`
- `request_fingerprint`
- audit stream linkage (`stream_id`, `prev_event_hash`, sequence constraints)
- a supervisor-issued permit object

## 2. Canonical Permit Token Structure

Canonical hash domain:
- `secure_execution_layer.execution_permit.v1`

Permit object (canonical JSON input):

```json
{
  "permit_id": "<deterministic-id>",
  "policy_hash": "<hash>",
  "request_fingerprint": "<hash>",
  "capability": {
    "kind": "tool|net_egress|secret_use",
    "selector": "<deterministic-selector>"
  },
  "decision": "allow|warn|block|review",
  "severity_to_gating": {
    "allow": "proceed",
    "warn": "proceed_emit_audit",
    "block": "deny_emit_audit",
    "review": "pause_pending_ledger"
  },
  "issued_by": "<supervisor-identity>",
  "issued_at_sequence": 0,
  "stream_id": "<audit-stream-id>",
  "prev_event_hash": "<chain-tip-hash>",
  "permit_scope": {
    "mode": "one_shot|bounded",
    "selector": "<scope-selector>"
  },
  "expiry_condition": {
    "type": "valid_for_sequence_range|valid_for_commit",
    "sequence_range": [0, 0],
    "commit_sha": null
  }
}
```

Deterministic ID rule:
- `permit_id` MUST be derived from canonical permit body hash.
- Recommended construction: hash the permit body excluding `permit_id`, then set `permit_id` to that hash (or domain-separated derivative).

Forbidden fields/bases:
- wall-clock timestamp validity
- random nonce
- runtime-only, process-local, or environment-dependent fields

## 3. Deterministic Validity Rules (Executor-side)

Verification MUST be pure and fail-closed:

1. Recompute `policy_hash` and `request_fingerprint` from deterministic canonical inputs.
2. Recompute permit body hash and verify `permit_id` derivation.
3. Verify `stream_id` matches current audit stream.
4. Verify `prev_event_hash` equals current chain tip for that stream.
5. Verify sequence validity:
   - `one_shot`: `issued_at_sequence` must match exact permitted sequence.
   - `bounded`: sequence must lie within declared deterministic range.
6. Verify decision semantics:
   - `block`: MUST NOT execute
   - `warn`: MAY execute, MUST emit warning audit event
   - `review`: MUST NOT execute unless required review artifact is present and valid
   - `allow`: MAY execute only if all checks pass
7. Any mismatch, missing required field, invalid enum, or non-canonical object => deny (fail-closed).

Executor MUST NOT auto-correct malformed permits.

## 4. Mandatory Review Coupling

If `decision = review`, permit MUST include:
- `review_ref.review_id`
- `review_ref.review_type`

`review_id` derivation MUST be deterministic from:
- `policy_hash`
- `request_fingerprint`
- `review_type`

Replay requirement:
- `governance/reviews/<review_id>.review.json` MUST exist in the evaluated Git state.
- Missing artifact or mismatched content => deny (fail-closed).

## 5. Authority Boundaries

- Supervisor: canonical issuance authority.
- Executor: verification/enforcement instrument only.
- Governance (Git): source of truth for policy and review artifacts.

Prohibited:
- executor self-issuance
- executor policy mutation to satisfy permit verification
- runtime override paths that bypass permit verification

## 6. Replay Contract Integration

Permit attestation MUST be replayable without external state:
- Permit issuance MUST be represented as an audit event (or deterministically reflected by one).
- Permit verification inputs MUST be derivable from:
  - current Git state
  - deterministic request input
  - deterministic audit chain state

No dependency on:
- clock time
- external cache
- non-deterministic network responses

## 7. Minimal Validation Contract (Machine-checkable)

Required fields:
- `permit_id`
- `policy_hash`
- `request_fingerprint`
- `capability`
- `decision`
- `severity_to_gating`
- `issued_by`
- `issued_at_sequence`
- `stream_id`
- `prev_event_hash`
- `permit_scope`
- `expiry_condition`

Constraints:
- `decision` enum: `allow|warn|block|review`
- additional properties: forbidden by default
- expiry condition type: deterministic enum only

## 8. Non-goals (v0.1)

This spec intentionally does NOT define:
- cryptographic signature implementation
- supervisor runtime attestation service
- executor runtime dispatch wiring
- persistence engine for permit storage
- orchestrator integration flow

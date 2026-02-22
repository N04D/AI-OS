# Supervisor Execution Permit Issuance Flow v0.1

Status: Experimental
Scope: Specification only (no runtime wiring)

## 1. Purpose

This specification defines a deterministic, replayable, governance-bound permit issuance flow.

Supervisor role:
- Canonical policy interpretation authority
- Sole execution-permit issuance authority
- Bound to governance policy and PR-gated mutation constraints
- Prohibited from bypassing review-ledger requirements

Threat model:
- Shadow autonomy (execution without governed permit issuance)
- Supervisor drift (policy interpretation divergence)
- Implicit authority expansion (unapproved trust-lift)
- Replay desynchronization (non-reproducible permit issuance)

## 2. Preconditions for Permit Issuance

Supervisor MAY issue a permit only when all preconditions hold:

1. `policy_hash` resolved from governed policy state in Git.
2. `request_fingerprint` computed deterministically from request inputs.
3. Policy-to-capability evaluation completed.
4. Conflict resolution rules applied deterministically.
5. Severity-to-gating mapping resolved deterministically.
6. Review ledger consulted if severity resolves to `review`.
7. Current audit stream tip known (`stream_id`, `sequence`, `prev_event_hash`).

Forbidden:
- Runtime-only decisions that cannot be replayed
- Time-based overrides
- Non-ledgered review approvals
- Permit issuance without corresponding audit event

## 3. Deterministic Issuance Procedure

All steps MUST be derivable from Git state + deterministic request input.
No entropy, no clock dependency, no hidden runtime state.

Step 1. Evaluate policy -> decision
- Apply canonical policy interpretation contract.
- Resolve `decision` and deterministic gating mapping.

Step 2. Derive permit body
- Construct permit fields exactly as defined by Execution Permit Attestation Contract v0.1.
- Exclude wall-clock validity and random fields.

Step 3. Compute `permit_id`
- Compute via canonical domain hash over permit body.
- Domain: `secure_execution_layer.execution_permit.v1`.

Step 4. Emit issuance audit event
- `event_type = "permit.issued"`.
- Event payload MUST include:
  - `policy_hash`
  - `request_fingerprint`
  - `permit_id`
  - `stream_id`
  - `sequence`
  - `prev_event_hash`

Step 5. Return permit object
- Return canonical permit object only if all prior steps are valid.
- Any mismatch or missing required input => fail-closed (no permit issuance).

## 4. Review Case Handling

If `decision == review`:

Supervisor MUST:
1. Derive `review_id` deterministically from:
   - `policy_hash`
   - `request_fingerprint`
   - `review_type`
2. Verify `governance/reviews/<review_id>.review.json` exists in evaluated Git state.
3. Include `review_id` in permit object.
4. Issue permit only after ledger artifact existence and consistency checks pass.

Prohibited:
- Supervisor self-approval without ledger artifact
- Implicit trust escalation in review path

## 5. Authority Boundaries

| Layer | Allowed Responsibilities | Prohibited |
|---|---|---|
| Supervisor | Interpret policy, issue permit, emit issuance audit event | Autonomous governance mutation, ledger bypass |
| Executor | Verify permit, enforce permit decision | Permit issuance |
| Governance (Git) | Source of policy truth, review truth, commit truth | Runtime decision override |

Additional prohibitions:
- Supervisor MUST NOT modify `governance/policy` autonomously.
- Executor MUST NOT issue permits.
- Orchestrator MUST NOT bypass permit requirement.

## 6. Replay Contract Integration

Permit issuance MUST be reproducible from:
- `policy_hash`
- `request_fingerprint`
- deterministic audit chain state

Replay invariants:
1. Replaying same governed inputs MUST regenerate identical `permit_id`.
2. Permit issuance audit event MUST be chain-validatable.
3. Replay divergence on policy/chain/review artifacts MUST fail-closed.

Fail-closed triggers:
- policy mismatch
- chain mismatch
- review artifact mismatch

## 7. Non-Goals

This specification intentionally does NOT define:
- Cryptographic signature format
- Key storage/management
- Network distribution protocol
- Runtime dispatch integration
- Kill-switch implementation

## 8. Deterministic Data Contract Notes

- Issuance validity MUST NOT depend on wall-clock timestamps.
- Sequence-based and Git-state-based constraints are permitted.
- Floats are disallowed in deterministic issuance-critical fields.
- No implicit defaults for required issuance fields.

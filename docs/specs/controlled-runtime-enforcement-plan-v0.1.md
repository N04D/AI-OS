# Controlled Runtime Enforcement Plan v0.1

Status: Experimental
Scope: Specification only (no runtime implementation)

## 1) Purpose

This plan defines minimal, controlled runtime wiring boundaries for existing secure execution contracts:
- policy-to-capability deterministic mapping
- execution permit issuance
- execution permit validation
- replay verifier
- audit chain integrity

Objectives:
- prevent shadow autonomy and bypass paths
- enforce fail-closed behavior at each boundary
- preserve determinism (no hidden state, no time-based gating)

## 2) Runtime Insertion Points (Hook Points)

### A) Supervisor Hook: Decision & Permit Issuance Boundary

Inputs:
- governed policy snapshot (`policy_hash` derivable)
- deterministic request descriptor
- audit chain tip (`stream_id`, `sequence`, `prev_event_hash`)

Outputs:
- permit object proposal
- issuance audit event proposal (`event_type=permit.issued`)

Fail-closed conditions:
- missing or non-canonical policy input
- ambiguous mapping/conflict result
- permit body hash mismatch
- unresolved review prerequisites
- missing chain-tip binding inputs

### B) Executor Hook: Permit Verification Boundary

Inputs:
- permit object
- local execution request descriptor
- current audit chain tip

Verification sequence:
1. permit structure validation
2. `permit_id` recomputation
3. chain binding validation (`stream_id`, `sequence`, `prev_event_hash`)

Outputs:
- verified permit => continue to execution boundary
- invalid permit => halt action + emit deterministic denial event (conceptual)

### C) Executor Hook: Secure Execution Boundary

Rule:
- executor executes only under a verified permit

Boundary constraints:
- executor MUST NOT interpret policy
- executor enforces permit outcome only

### D) Replay Hook: Replay Verification Boundary

Replay mode verifies:
- audit chain integrity
- permit issuance consistency
- required review artifacts existence and matching hashes

Fail-closed on any mismatch.

## 3) Fail-Closed Contracts

Canonical error taxonomy (minimum set):
- `secure_layer.enforce.invalid_permit`
- `secure_layer.enforce.chain_mismatch`
- `secure_layer.enforce.policy_mismatch`
- `secure_layer.enforce.review_missing`
- `secure_layer.enforce.ambiguous_mapping`
- `secure_layer.enforce.unbound_request`
- `secure_layer.enforce.replay_mismatch`

Hook-level failure classes:
- input validation failure
- deterministic mismatch failure
- missing artifact failure
- ambiguous config failure

Continuation rule:
- no warn-and-continue path except explicit permit `decision=warn`

## 4) Review Handling in Runtime

Review decision rule:
- `review` is non-executable until review artifact is present and valid

Supervisor constraint:
- supervisor may issue executable allow/block only after ledgered review resolution

Executor constraint:
- executor treats `review` as non-executable

Resume protocol:
- resume requires Git-visible `governance/reviews/<review_id>.review.json`
- replay verifier confirms policy/request hash consistency before resume

## 5) Kill-Switch Semantics (Spec Only)

Conceptual triggers:
- audit chain integrity failure
- permit replay inconsistency
- permit `policy_hash` mismatch with current governed snapshot
- execution attempt without permit (hard invariant violation)

Conceptual response:
1. stop current cycle immediately
2. enter blocked state pending human intervention or higher-trust phase gate

## 6) Mode Separation

### A) Live Mode
- permit required per action
- chain tip binding required per action
- fail-closed on verification mismatch

### B) Replay Mode
- no new permit issuance
- verification against recorded artifacts only
- no side effects allowed

## 7) Minimal Wiring Order (Safe Sequence)

Step 0: freeze specs/schemas
Step 1: add interface-level adapter stubs (future)
Step 2: wire executor permit verification boundary
Step 3: wire supervisor issuance boundary
Step 4: wire audit emission points
Step 5: enable kill-switch triggers

Constraint:
- steps MUST NOT be executed out of order

## 8) Non-Goals

This plan explicitly excludes:
- signing and key management
- network enforcement adapters
- persistent audit sink design
- autonomous policy mutation
- PR-gate automation logic
- multi-agent memory merge logic

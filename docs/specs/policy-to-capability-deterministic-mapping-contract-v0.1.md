# Policy-to-Capability Deterministic Mapping Contract v0.1

Status: Experimental
Scope: Specification only (no runtime wiring)

## 1. Purpose

This contract defines the deterministic transformation pipeline:

`policy rules -> selector matching -> conflict resolution -> severity -> severity-to-gating -> permit decision`

Threat model:
- implicit supervisor interpretation drift
- unordered rule evaluation
- non-deterministic conflict resolution
- hidden severity escalation
- replay divergence

## 2. Canonical Inputs

Required mapping inputs:
- `policy_hash` (governed policy snapshot)
- `capability_sets` (derived from governed capabilities policy structures)
- request descriptor (tool/net/secret)
- `conflict_resolution` configuration
- `severity_to_gating` mapping

Input constraints:
- fully specified
- canonicalizable
- hash-stable
- no implicit defaults

Missing required input MUST fail-closed.

## 3. Deterministic Rule Matching

Matching semantics MUST be declared per rule family:
- exact
- prefix
- regex (only if explicit, deterministic, and anchored constraints are declared)

Ordering requirement MUST be explicit:
- `explicit_priority`, or
- `stable_order_mode` (`lexical_rule_id` | `order_index`)

Prohibited:
- dictionary iteration order as evaluation order
- first-match behavior without declared deterministic ordering
- ambiguous overlap without explicit tie-break
- undeclared fallback defaults

## 4. Conflict Resolution Contract

Allowed modes:
- `deny_wins`
- `most_specific`
- `explicit_priority`

For every mode, policy MUST declare:
- tie-break semantics
- equal-priority/equal-specificity behavior

Ambiguity MUST fail-closed. Silent resolution is prohibited.

## 5. Severity Determination

Rule outcome MUST carry explicit severity:
- `allow`
- `warn`
- `block`
- `review`

Severity constraints:
- explicitly declared in policy
- never inferred from runtime conditions
- no implicit escalation/de-escalation

Prohibited:
- supervisor severity escalation outside governed policy
- runtime mutation of severity
- severity override without ledgered review artifact

## 6. Severity-to-Gating Binding

Severity MUST bind to machine-declared gating outcome.

Reference mapping pattern:
- `allow -> permit allow`
- `warn -> permit warn`
- `block -> permit block`
- `review -> permit review` (ledger artifact required)

Binding requirements:
- declared in governed policy/state
- replay-verifiable
- no hardcoded hidden mapping path

## 7. Deterministic Output Object

Canonical mapping result object:

```json
{
  "policy_hash": "...",
  "request_fingerprint": "...",
  "matched_rule_id": "...",
  "conflict_resolution_mode": "deny_wins|most_specific|explicit_priority",
  "final_severity": "allow|warn|block|review",
  "final_gating": "permit_allow|permit_warn|permit_block|permit_review",
  "capability_descriptor": {
    "kind": "tool|net_egress|secret_use",
    "selector": "..."
  }
}
```

Output requirements:
- hashable via canonical hash contract
- serializable as audit event payload
- directly consumable by permit issuance flow

## 8. Replay Integration

Replay invariants:
- mapping is re-derivable from `policy_hash + request input + governed mapping config`
- replay MUST produce identical `matched_rule_id` and `final_severity`
- mismatch MUST fail-closed

Prohibited:
- runtime-only caches as mapping authority
- external mutable state dependency for mapping result

## 9. Authority Boundaries

Supervisor:
- performs deterministic mapping
- MUST NOT override mapping outcome

Executor:
- consumes mapping result through permit contract
- MUST NOT apply fallback mapping logic

Governance (Git):
- defines mapping rules and conflict/severity contracts

Prohibited:
- supervisor interpretation drift
- executor fallback policy interpretation
- orchestrator policy interpretation/override

## 10. Non-Goals

This specification does NOT define:
- runtime dispatch integration
- signing
- PR merge logic
- commit mutation
- kill-switch wiring

## 11. Validation Profile (Machine-checkable)

Required fields in mapping result:
- `policy_hash`
- `request_fingerprint`
- `matched_rule_id`
- `conflict_resolution_mode`
- `final_severity`
- `final_gating`
- `capability_descriptor`

Validation requirements:
- strict enums for severity and conflict mode
- `additionalProperties: false` by default
- no floats in deterministic core fields


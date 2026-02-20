# Roadmap: Secure Execution Layer

Milestone: Secure Execution Layer
Status: Proposed (research-to-spec hardening)
Type: Governance-first adoption plan (no runtime import)

## Scope Statement
This roadmap extracts and hardens security patterns, not runtime architecture.

Will be imported:
- Deterministic capability policy contract
- Deterministic network egress policy contract
- Secrets boundary contract with reduced leak surface
- Severity->gating machine contract
- Review-ledger artifact contract
- Replay-safe audit event contract

Will NOT be imported:
- IronClaw orchestrator/worker runtime stack
- IronClaw DB schema as mandatory AI-OS dependency
- Runtime-only review state
- Any implicit trust-lift from userland integrations

## Epic 1: Deterministic Policy Contracts
Tasks:
1. Harden `capabilities.schema.json` with conflict resolution + tie-breaker contract.
2. Harden `network-egress.schema.json` with conflict resolution + wildcard constraints.
3. Harden `secrets-boundary.schema.json` with disallowed leak-prone modes by default.
4. Remove ambiguous schema branches that allow implementation-specific interpretation.

Acceptance Criteria:
- Every overlapping ruleset declares deterministic conflict resolution.
- Tie-break behavior is machine-specified.
- Unknown/ambiguous policy states fail-closed.

## Epic 2: Severity and Review Ledgering
Tasks:
1. Define severity->gating mapping as machine contract.
2. Define review decision artifact schema/path in governance ledger.
3. Define deterministic resume checks on policy hash + request fingerprint.

Acceptance Criteria:
- `review` cannot be resolved in runtime-only memory.
- Resume without matching ledger artifact is fail-closed.

## Epic 3: Secrets + Egress Hardening
Tasks:
1. Disallow `query_param` and `url_path` injection by default.
2. Add constrained exception mechanism (`review` + TTL + justification).
3. Require deterministic DNS replay contract (`pinned_ips` or snapshot hash).

Acceptance Criteria:
- High-leak injection paths require explicit short-lived exception.
- Wildcard egress cannot bypass explicit path and depth controls.

## Epic 4: Userland Trust Boundaries
Tasks:
1. Explicitly prohibit userland trust-lift without PR-gated policy update.
2. Require review artifact for any trust-zone elevation.
3. Keep MCP/external integration privileges policy-scoped and off by default.

Acceptance Criteria:
- Userland cannot gain kernel/supervisor authority implicitly.
- Trust-zone elevation is always reviewed and ledgered.

## Epic 5: Replay Integrity and Governance Integration
Tasks:
1. Formalize minimal replay-safe audit event contract.
2. Ensure security artifacts include policy hash for replay.
3. Add PR-gate checks to enforce schema/version consistency.

Acceptance Criteria:
- Security decisions are replayable from Git-tracked artifacts.
- Event ordering integrity is machine-checkable.

## Sequencing
1. Epic 1
2. Epic 2
3. Epic 3
4. Epic 4
5. Epic 5

## Risk Control Notes
- Keep fail-closed defaults on all high-risk paths.
- Any runtime ambiguity in interpretation authority blocks progression.

# Roadmap Patch: IronClaw Pattern Extraction into AI-OS

Milestone: Secure Execution Layer
Status: Proposed
Type: Governance-first adoption plan (no runtime import)

## Scope Statement
This roadmap extracts security patterns, not architecture.

Will be imported:
- Capability policy contract
- Egress policy contract
- Secret boundary contract
- Security event taxonomy
- Deterministic supervisor checks

Will NOT be imported:
- IronClaw orchestrator/worker runtime stack
- IronClaw DB schema as a mandatory AI-OS dependency
- Full extension marketplace/installer UX
- Any non-deterministic or opaque runtime state model

## Epic 1: Security Policy Contracts
Tasks:
1. Define `capabilities.schema.json` and integrate into governance policy loading.
2. Define `network-egress.schema.json` with allowlist-first semantics.
3. Define `secrets-boundary.schema.json` with host-only injection rules.
4. Add schema validation gate to supervisor policy load path.

Acceptance Criteria:
- Policy files fail closed when schema-invalid.
- Policy hash remains part of decision artifacts.
- Unknown capability or egress rule cannot default to allow.

Dependencies:
- Existing policy loader (`supervisor/pr_gate/policy_loader.py`).

## Epic 2: Deterministic Security Evaluation in Supervisor
Tasks:
1. Add security decision layer that maps action -> `block/warn/review/allow`.
2. Extend governance artifacts with security decision records.
3. Add policy violation reporting to governance status publication.

Acceptance Criteria:
- Same input + policy hash yields identical decisions.
- `policy.violation` events are visible in artifacts/logs.
- Missing rules produce `block`.

Dependencies:
- Epic 1 schemas and policy loading.

## Epic 3: Executor Enforcement Adapters
Tasks:
1. Add capability check hook before tool execution.
2. Add network egress check hook before outbound calls.
3. Add secret injection boundary hook with alias-only input.
4. Add size/timeout budget checks from policy.

Acceptance Criteria:
- Executor cannot execute undeclared capabilities.
- Outbound requests require matching allowlist rule.
- Tool code cannot receive plaintext secret values.
- Denied actions emit auditable events.

Dependencies:
- Epic 1 schemas, Epic 2 decision model.

## Epic 4: Security Telemetry and Replayability
Tasks:
1. Standardize event types: `tool.exec`, `net.req`, `secret.use`, `policy.violation`.
2. Add deterministic event serializer with policy hash linkage.
3. Add replay checker for security decision determinism.

Acceptance Criteria:
- Security events include policy hash/version and correlation id.
- Replay check confirms deterministic outcomes.
- Security event stream can be audited without hidden state.

Dependencies:
- Epic 2 decision model, Epic 3 enforcement hooks.

## Epic 5: Hardening and Governance Rollout
Tasks:
1. Start in `warn` mode for low-risk paths.
2. Promote high-risk paths to `block` mode.
3. Add PR-gate checks requiring security schema consistency.
4. Publish operator guidance for capability/egress/secrets policy authoring.

Acceptance Criteria:
- High-risk path changes cannot bypass security policy checks.
- Governance artifacts contain clear violation reasons.
- Documentation exists for safe rollout and rollback.

Dependencies:
- Epics 1-4 completed.

## Sequencing
1. Epic 1
2. Epic 2
3. Epic 3
4. Epic 4
5. Epic 5

## Risk Control Notes
- Keep rollout fail-closed for high-risk paths, phased for low-risk paths.
- Treat MCP/federated tool protocols as experimental userland until policy parity exists.

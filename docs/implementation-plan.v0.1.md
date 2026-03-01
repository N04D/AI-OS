# Implementation Plan v0.1

## Purpose
Provide a safe, incremental, test-first execution blueprint for evolving AI-OS architecture with deterministic behavior and fail-closed controls.

## Architecture Overview
| Component | Responsibility | Trust Boundary |
|---|---|---|
| Kernel | Immutable core governance and safety contracts | Highest trust, externally managed |
| Supervisor | Runtime orchestration, permit enforcement, PR-gate invocation | Trusted control plane |
| PR-Gate | Deterministic merge policy evaluation and status publication | Trusted policy decision point |
| Plugins | Optional extensibility units with explicit manifests and capabilities | Tiered trust (official/community/local) |
| Gateways | Inbound channel adapters and protocol normalization | Untrusted ingress boundary |
| Skills | Task-level tool modules (userland and restricted system-ops) | Constrained execution boundary |
| User Governance | UI-managed operator policy and approvals | Scoped by role and policy schema |
| System Ops Executor | Restricted maintenance/evolution execution path | Elevated, explicitly gated |

## Trust Model

### Kernel Governance
- Kernel governance is immutable through runtime channels.
- Any kernel change requires repository review path and policy checks.
- Runtime components must treat kernel policy load or parse failures as deny/stop.

### User Governance
- User governance is operator-managed through typed schemas and UI workflows.
- User policy cannot override kernel safety invariants.
- Missing or invalid user policy evaluates to deny (fail-closed).

### Plugin Trust Tiers
| Tier | Source | Defaults | Upgrade Path |
|---|---|---|---|
| Official | First-party signed/verified plugins | Allowed within declared capabilities | Standard release review |
| Community | Third-party plugins | Disabled by default | Explicit operator approval |
| Local | Repo-local custom plugins | Disabled by default | Local review + capability checks |

### Channel Boundary Rules
- Inbound gateways normalize external input into typed events.
- External channels cannot directly invoke kernel/system-ops actions.
- All channel-driven actions require policy evaluation and auditable decision records.

### System Ops Boundary
- System ops actions must run in a separate executor path with explicit permits.
- No free-form system mutation from userland skills or chat channels.
- Permit issuance must be deterministic, logged, and revocable.

## Milestones

## Milestone 1: Gitea-native PR-Gate Enforcement
### Objectives
- Enforce path allowlist in Gitea CI using deterministic evaluator.
- Publish clear required check context: `pr-gate/path-allowlist`.
- Fail closed on parse/API/runtime errors.

### Files to Create
- `.gitea/workflows/pr-gate.yml`
- `docs/gitea-ci-setup.md`
- `tests/test_pr_gate_gitea_workflow.py` (integration/contract test)

### Tests Required
- Unit tests for evaluator logic (allow, violation, missing policy, rename).
- Workflow contract test: trigger/event, check name, evaluator command present.

### Acceptance Criteria
- Pull request events run PR-gate workflow.
- Non-zero evaluator exit fails CI.
- Required check name is exactly `pr-gate/path-allowlist`.
- `gate-verdict.json` generated in CI run workspace.

### Failure Modes
- Missing policy file -> deny.
- Invalid policy parse -> deny.
- Git API fetch failure -> deny.
- Workflow misconfiguration (wrong event/check name) -> detected by tests.

### Completion Checklist (Milestone 1)
- [ ] `.gitea/workflows/pr-gate.yml` exists and triggers on PR `opened|synchronize|reopened`.
- [ ] Required check name is exactly `pr-gate/path-allowlist`.
- [ ] Evaluator command runs `scripts/pr_gate_path_allowlist.py` with policy path `.gitea/governance/path-allowlist.v1.yaml`.
- [ ] Workflow emits `gate-verdict.json` and fails closed on missing token/API base/evaluator error.
- [ ] Documentation exists at `docs/gitea-ci-setup.md` with branch protection requirements.
- [ ] Contract and unit tests pass locally:
  - `bash scripts/test-pr-gate-m1.sh`
- [ ] Branch protection in Gitea is configured to require `pr-gate/path-allowlist`.

## Milestone 2: Plugin Loader + Boundary Validator
### Objectives
- Add deterministic plugin discovery and schema validation.
- Enforce capability allowlist before plugin activation.

### Files to Create
- `supervisor/plugins/loader.py`
- `supervisor/plugins/validator.py`
- `docs/plugins-boundary.v0.1.md`
- `tests/test_plugin_loader.py`
- `tests/test_plugin_boundary_validator.py`

### Tests Required
- Manifest parsing and signature handling tests.
- Capability mismatch fail-closed tests.

### Acceptance Criteria
- Invalid manifest blocks plugin load.
- Unknown capability blocks plugin load.
- Deterministic load order and stable hashes.

### Failure Modes
- Manifest parse error -> plugin disabled.
- Policy mismatch -> plugin disabled.
- Missing validator dependency -> all plugins disabled (safe mode).

## Milestone 3: Channel Split (Outbound Plugins vs Inbound Gateways)
### Objectives
- Separate inbound protocol handling from outbound side-effect plugins.
- Prevent inbound channels from directly invoking outbound/system paths.

### Files to Create
- `supervisor/gateways/` modules
- `supervisor/plugins/outbound/` modules
- `docs/channel-boundaries.v0.1.md`
- `tests/test_gateway_boundary.py`

### Tests Required
- Channel-to-action routing tests.
- Unauthorized action attempts deny tests.

### Acceptance Criteria
- Inbound messages become normalized events only.
- Outbound side effects require explicit policy pass.

### Failure Modes
- Ambiguous route mapping -> deny.
- Missing policy decision -> deny.

## Milestone 4: Skill Framework (Userland vs System Ops)
### Objectives
- Split skills into userland and system-ops classes.
- Require permits for system-ops skill execution.

### Files to Create
- `supervisor/skills/framework.py`
- `supervisor/skills/registry.py`
- `docs/skill-boundaries.v0.1.md`
- `tests/test_skill_framework.py`

### Tests Required
- Userland allow path tests.
- System-ops permit-required tests.

### Acceptance Criteria
- Userland skills cannot mutate protected paths.
- System-ops skills blocked without valid permit.

### Failure Modes
- Skill class unknown -> deny.
- Permit validation failure -> deny.

## Milestone 5: User Governance + UI
### Objectives
- Add UI-managed user policy with schema validation and audit trail.
- Ensure policy updates are reviewable and reversible.

### Files to Create
- `app/ui/governance/*` (or equivalent frontend path)
- `supervisor/governance/user_policy.py`
- `docs/user-governance-ui.v0.1.md`
- `tests/test_user_policy_validation.py`

### Tests Required
- Schema validation tests.
- Policy precedence tests (kernel > user).

### Acceptance Criteria
- Invalid user policy cannot be saved/applied.
- Policy changes produce immutable audit records.

### Failure Modes
- Storage/write failure -> previous policy remains active.
- Schema mismatch -> reject update.

## Milestone 6: Self-Evolution + System Ops Executor
### Objectives
- Introduce constrained self-evolution workflow.
- Route all privileged maintenance tasks through system-ops executor.

### Files to Create
- `supervisor/system_ops/executor.py`
- `supervisor/system_ops/permit_gate.py`
- `docs/system-ops-executor.v0.1.md`
- `tests/test_system_ops_executor.py`

### Tests Required
- Permit issuance/expiry tests.
- Replay prevention tests.
- Immutable ledger linkage tests.

### Acceptance Criteria
- No privileged action without permit.
- All actions linked to request -> permit -> result chain.

### Failure Modes
- Permit replay detected -> deny and alert.
- Missing ledger write -> stop execution.

## Non-Goals
- No remote kernel control via Telegram or other external chat channels.
- No free-form execution from external channels.
- No in-process plugin loading without validation boundary.
- No governance mutation via skills.

## Iteration Strategy
- Each milestone is independently testable and shippable behind explicit boundaries.
- Every new component ships with unit tests and deterministic fixtures.
- Integration tests are added only after unit-level fail-closed behavior is verified.
- CI requirements per milestone:
  - Run unit tests for changed components.
  - Run boundary/policy contract tests.
  - Enforce required check contexts (starting with `pr-gate/path-allowlist`).
- If CI environment capability is missing, document the gap and stop instead of bypassing controls.

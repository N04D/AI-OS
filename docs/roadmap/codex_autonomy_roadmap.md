# AI-OS Codex Autonomy Roadmap

Status: Phase 4
Authority: Supervisor (Human)  
Promotion Model: Earned Autonomy  
Fail-Closed: Always

---

## Rules

- Codex may only mark checkboxes.
- Codex may NOT change phase status.
- Promotion requires explicit supervisor approval.
- All changes must preserve deterministic behavior.
- Governance may never be weakened.

---

# Phase 1 — Runtime Consolidation

## Objective
Unify and stabilize the runtime control plane.

## Tasks

- [x] Remove legacy budget overlap (supervisor/autonomy_budget.py)
- [x] Verified unused
- [x] Eliminate implicit `origin` remote assumptions
- [x] Confirm Gitea is canonical runtime remote
- [x] Ensure night_mode flows through supervisor kernel
- [x] Verify mutation boundary restricts allowed files only
- [x] Confirm deterministic JSON serialization where required
- [x] Confirm UTC-only time handling in scheduler/budgets

## Validation Criteria

- [x] No duplicate budget logic paths remain
- [x] No implicit remote assumptions
- [x] Night mode executes without manual intervention
- [x] No fail-open behavior detected
- [x] No broad `git add .` in governed flows

Phase 1: ACCEPTED

---

# Phase 2 — Deterministic Night Autonomy

## Objective
Night run must be reproducible and stable.

## Tasks

- [x] Night mode executes full autonomy loop
- [x] Scheduler deterministic ordering confirmed
- [x] Budget consumption recorded deterministically
- [x] Status publication to Gitea verified
- [x] No non-deterministic timestamps outside controlled areas

## Validation Criteria

- [x] 3 consecutive successful night runs
- [x] Identical output for identical state
- [x] Audit artifacts produced consistently
- [x] No governance bypass possible

## Execution Plan (Phase 2)

- [x] Step 1: Baseline Phase 2 scope vs current code/tests (status: completed)
- [x] Step 2: Identify objective/criteria gaps (status: completed)
- [x] Step 3: Implement minimal Phase 2 runtime changes (status: completed)
- [x] Step 4: Add/update deterministic scheduler and budget tests (status: completed)
- [x] Step 5: Add/update Gitea status publication verification tests (status: completed)
- [x] Step 6: Add/update timestamp determinism guards/tests (status: completed)
- [x] Step 7: Run and stabilize targeted Phase 2 tests (status: completed)
- [x] Step 8: Run full test suite and fix Phase 2 regressions (status: completed)
- [x] Step 9: Update roadmap and progress with evidence (status: completed)
- [x] Step 10: Publish completion report and HALT (status: completed)

## Remediation Plan (Conditional Acceptance)

- [x] Remediation 1: Normalize plugin-loader tests to environment Python (`sys.executable`)
- [x] Remediation 2: Make Phase-K policy-path tests environment-agnostic
- [x] Remediation 3: Add explicit skip justification if policy file is unavailable
- [x] Remediation 4: Re-run full `pytest -q` and verify zero failures

Phase 2: ACCEPTED

---

# Phase 3 – Supervisor Hardening & Control Plane

## Objective
Harden supervisor control-plane enforcement with explicit authorization, deterministic halt behavior, strict boundaries, and integrity checks.

## Tasks

- [x] 3.1 Approval Token Mechanism (Hard Gate)
- [x] 3.2 Deterministic Interrupt Mechanism
- [x] 3.3 Supervisor Boundary Hardening
- [x] 3.4 State Integrity Verification
- [x] 3.5 Permanent Phase Acceptance Rule

## Validation Criteria

- [x] Execution without valid token denied
- [x] Token reuse rejected deterministically
- [x] Expired token fails closed
- [x] Interrupt leads to deterministic HALT with persisted state
- [x] No governance-core boundary bypasses
- [x] State tampering detected and denied (fail-closed)
- [x] Phase completion blocked when contract requirements fail
- [x] Full pytest suite green

## Phase 3 Scope Details

### 3.1 Approval Token Mechanism (Hard Gate)
- [x] Add approval token structure (scope-bound, time-bound, single-use)
- [x] Implement token validation in supervisor layer only
- [x] Store token hash (SHA256) in audit log (never plaintext)
- [x] Reject expired or reused tokens
- [x] Integrate token requirement into:
  - phase start
  - budget override paths
  - high-risk autonomy actions

### 3.2 Deterministic Interrupt Mechanism
- [x] Add `INTERRUPT_FLAG` in autonomy state
- [x] Check interrupt at:
  - scheduler tick
  - before budget consume
  - at phase boundary
- [x] On interrupt:
  - finish current atomic action
  - persist state
  - enter HALT
  - log interrupt event

### 3.3 Supervisor Boundary Hardening
- [x] Enforce canonical supervisor interface for:
  - budget
  - scheduler
  - task materialization
- [x] Add static import scan test:
  - detect direct governance-core imports outside supervisor boundary
- [x] Refactor bypass paths if detected

### 3.4 State Integrity Verification
- [x] Compute SHA256 hash for:
  - autonomy state
  - budget state
- [x] Store reference hash in controlled metadata
- [x] Validate integrity before execution
- [x] On mismatch:
  - fail-closed
  - log integrity violation

### 3.5 Permanent Phase Acceptance Rule
- [x] Add governance rule document defining:
  - full suite must pass
  - roadmap updated
  - progress updated
  - HALT entered
- [x] Add automated verification test:
  - block phase completion if any failures exist

## Execution Plan (Phase 3)

- [x] Step 1: Replace legacy Phase 3 roadmap bullets with hardening scope + acceptance checks (status: completed)
- [x] Step 2: Implement approval token validator + audit hashing + single-use store (status: completed)
- [x] Step 3: Wire token gate into phase start, budget override, and high-risk actions (status: completed)
- [x] Step 4: Add deterministic interrupt flag handling and HALT artifacts (status: completed)
- [x] Step 5: Add canonical supervisor boundary interface and static bypass scan test (status: completed)
- [x] Step 6: Add state integrity metadata + pre-execution verification (status: completed)
- [x] Step 7: Add permanent phase acceptance rule document + enforcement test (status: completed)
- [x] Step 8: Run targeted tests for each hardening stream and stabilize (status: completed)
- [x] Step 9: Run full `pytest -q` and fix regressions until zero failures (status: completed)
- [x] Step 10: Update roadmap/progress evidence and enter HALT state (status: completed)

---

# Phase 4 — Bounded Self-Improvement

## Objective
Codex may propose and implement internal improvements strictly under governance.
Self-improvement is allowed only as work — never as authority.

- [x] Auditable
- [ ] Deterministic
- [x] Fail-closed
- [x] Budget-accounted
- [x] Boundary-enforced

## Tasks

### 4.1 Improvement Proposal Pipeline (PR-Only)
- [x] Objective: All self-improvements must flow through a governed PR process.
- [x] Add canonical proposal template: `docs/specs/self_improvement_proposal.v0.1.md`
- [x] Proposal requires problem statement.
- [x] Proposal requires risk tier (LOW / MED / HIGH).
- [x] Proposal requires affected components.
- [x] Proposal requires determinism impact.
- [x] Proposal requires test plan (mandatory).
- [x] Proposal requires rollback strategy.
- [x] Require PR checklist for self-improvement changes.
- [x] Tag PRs with self-improvement label.
- [x] Require supervisor approval before merge.
- [x] Validation: No self-improvement merged without proposal template.
- [x] Validation: Proposal includes explicit risk tier.
- [x] Validation: Proposal includes deterministic test plan.
- [x] Validation: Full pytest suite passes before merge.

### 4.2 Allowed Change Boundary (Hard Constraints)
- [x] Objective: Prevent self-improvement from mutating governance authority.
- [x] Define allowlist for self-improvement changes.
- [x] Allowlist: `docs/`
- [x] Allowlist: `tests/`
- [x] Allowlist: Explicit runtime modules (if declared in proposal).
- [x] Denylist: Governance core (unless HIGH-risk + token).
- [x] Add static boundary scan test for PR validation.
- [x] Fail-closed if disallowed files modified.
- [x] Validation: Disallowed path modification -> denied.
- [x] Validation: Direct governance-core edits without HIGH-tier -> rejected.
- [x] Validation: All runtime changes include test updates.

### 4.3 Risk Classification & Approval Tokens (Tiered Control)
- [x] Objective: Improvements must be classified and gated by risk.
- [x] Risk tier LOW: Docs/tests only, no runtime change.
- [x] Risk tier MED: Refactor preserving behavior.
- [x] Risk tier HIGH: Scheduler, budget, governance, approval tokens, phase acceptance, integrity.
- [x] Define canonical risk-tier specification document.
- [x] Require approval token for HIGH-risk changes.
- [x] Require golden-determinism evidence for MED/HIGH.
- [x] Log tier classification in audit record.
- [x] Validation: HIGH-risk without token -> denied.
- [x] Validation: MED/HIGH without determinism evidence -> denied.
- [x] Validation: Audit log contains tier + decision.

### 4.4 Determinism Guardrails (Golden Evidence)
- [x] Objective: Ensure improvements preserve deterministic behavior.
- [x] Define `determinism_evidence.json` schema.
- [x] Add identical-input -> identical-output validation tests.
- [x] Ensure no uncontrolled timestamps introduced.
- [x] Require rerun consistency tests for runtime changes.
- [x] Validation: Identical state produces identical artifacts.
- [x] Validation: No wall-clock dependency in governance logic.
- [x] Validation: Determinism evidence included in PR.

### 4.5 Budget Accounting for Improvements
- [x] Objective: Self-improvement consumes autonomy budget.
- [x] Introduce improvement budget category.
- [x] Record PR ID + tier in audit.
- [x] Deny improvement if budget exhausted.
- [x] Fail-closed on corrupt budget state.
- [x] Validation: Improvement without budget -> denied.
- [x] Validation: Budget consumption deterministic and logged.
- [x] Validation: Corrupt state -> fixed deny code.

### 4.6 No Mutation Outside Governed Execution
- [x] Objective: Prevent direct runtime mutation outside PR workflow.
- [x] Enforce PR-only mutation rule.
- [x] Add test detecting direct write attempts.
- [x] Fail-closed on unauthorized mutation path.
- [x] Validation: Direct mutation attempt -> denied + audit.
- [x] Validation: Only governed workflow may modify runtime logic.

### 4.7 Integration with Phase Acceptance Rule
- [x] Objective: Self-improvement merges require phase acceptance verification.
- [x] Require phase-acceptance verify before merge.
- [x] Evidence includes full suite result (0 failed).
- [x] Evidence includes skip justifications.
- [x] Evidence includes roadmap update.
- [x] Evidence includes progress update.
- [x] Evidence includes HALT state.
- [x] Add negative tests for missing evidence.
- [x] Validation: Merge denied without acceptance evidence.
- [x] Validation: Full suite must be green.
- [x] Validation: Skips explicitly justified.

### 4.8 HALT Discipline for Self-Improvement
- [x] Objective: Prevent continuous self-expansion.
- [x] Enforce "HALT after PR creation" rule.
- [x] Require explicit authorization to implement beyond proposal.
- [x] Log awaiting-approval state.
- [x] Validation: No commits beyond proposal without authorization.
- [x] Validation: HALT state recorded after proposal.

## Validation Criteria

Phase 4 Exit Condition:
- [x] All self-improvement flows via governed PR.
- [x] Risk tiers enforced.
- [x] Approval tokens integrated for HIGH-risk.
- [x] Determinism preserved.
- [x] Budget accounted.
- [x] Phase acceptance verify integrated.
- [x] No red tests.
- [x] HALT discipline respected.

## Execution Plan (Phase 4)

- [x] Step 1: Add canonical self-improvement proposal template and checklist structure.
- [x] Step 2: Enforce PR-only proposal pipeline validation hooks.
- [x] Step 3: Implement hard boundary allowlist/denylist checks for self-improvement changes.
- [x] Step 4: Add/extend static boundary scan tests for Phase 4 constraints.
- [x] Step 5: Define and enforce LOW/MED/HIGH risk tier classification.
- [x] Step 6: Integrate HIGH-risk approval token requirement into self-improvement flow.
- [x] Step 7: Add determinism evidence schema + verification guardrails.
- [x] Step 8: Integrate improvement budget accounting and deterministic audit logs.
- [x] Step 9: Enforce no direct mutation outside governed workflow.
- [x] Step 10: Integrate phase-acceptance verification gate for self-improvement merges.
- [x] Step 11: Enforce HALT-after-proposal discipline with explicit authorization resume path.
- [x] Step 12: Run full suite, update roadmap/progress, produce report, enter HALT.

---

# Phase 5 — Autonomous Night-Run Integration

## Objective

Validate a fully governed autonomous night-run loop where:

- Issues are detected and processed deterministically
- Tasks are materialized via governed flow
- Capability requests are handled explicitly
- Budget and approval rules are enforced
- Execution halts when no issues remain

Self-execution must remain auditable, deterministic, fail-closed, and boundary-enforced.

---

# Test Scenario

## Setup

- Inject test issue in controlled test repository or mocked Gitea layer.
- Issue type: `self-improvement` with LOW or MED risk tier.
- If required capability is missing -> system must generate a capability request.
- No implicit auto-grant allowed.

---

# Required System Behavior

## Step 1 — Issue Detection

- Night mode pulls open issues.
- Issues are ordered deterministically.
- Issue is converted into governed task materialization.
- Audit artifact is logged for detection + materialization.

## Step 2 — Capability Handling

If required capability is not present:

- System creates `capability_request` object.
- Capability request is logged with reason.
- System enters waiting state OR denies execution.
- No silent auto-grant.

If capability is present:

- Continue normal governed processing.

## Step 3 — Execution

- Governed PR flow enforced.
- Risk tier classification validated.
- Budget consumed under `improvement` category.
- Determinism evidence generated (if runtime affected).
- Phase acceptance verify invoked when applicable.

## Step 4 — Completion

- Issue marked resolved/closed.
- Audit artifact written.
- Queue rechecked deterministically.
- If no remaining issues -> enter HALT.

---

# 5.1 Issue -> Task Loop

- [x] Night mode detects new issues.
- [x] Deterministic ordering enforced.
- [x] Task materialization via governed flow.
- [x] Audit artifact created per issue.
- [x] Issue closure verified after execution.

---

# 5.2 Capability Request System

- [x] Missing capability triggers `capability_request` object.
- [x] Capability request logged and auditable.
- [x] No silent auto-grant allowed.
- [x] Capability execution requires supervisor approval token.
- [x] Deny execution if approval token missing.

---

# 5.3 Autonomous Completion Loop

- [x] Process issues sequentially.
- [x] Respect budget limits.
- [x] Respect interrupt flag.
- [x] Re-check issue queue after each completion.
- [x] Stop when no issues remain.
- [x] Enter HALT deterministically.

---

# Validation Criteria

Phase 5 is complete only if:

- [x] Issue -> task -> execution loop is fully deterministic.
- [x] Capability request system is enforced and auditable.
- [x] No silent privilege escalation possible.
- [x] Budget consumption logged for each processed issue.
- [x] Negative tests prove denial without required capability token.
- [x] Full pytest suite passes (0 failed).
- [x] HALT entered when issue queue empty.

## Execution Plan (Phase 5)

- [x] Step 1: Baseline current night-run issue ingestion and deterministic ordering paths.
- [x] Step 2: Add/verify issue fixture injection via mocked Gitea or controlled test repo.
- [x] Step 3: Implement governed issue -> task materialization audit trail assertions.
- [x] Step 4: Implement capability-missing path to emit `capability_request` and fail/wait explicitly.
- [x] Step 5: Enforce no auto-grant behavior and require explicit supervisor token for capability execution.
- [x] Step 6: Enforce governed PR flow + risk-tier validation within autonomous execution.
- [x] Step 7: Enforce improvement-budget consumption per processed issue with deterministic logs.
- [x] Step 8: Generate/verify determinism evidence for runtime-affecting execution paths.
- [x] Step 9: Add completion-loop checks (queue recheck, close issue, deterministic HALT on empty queue).
- [x] Step 10: Add negative tests for missing capability token and unauthorized capability execution.
- [x] Step 11: Run targeted Phase 5 suites and stabilize.
- [x] Step 12: Run full `pytest -q`, update roadmap/progress evidence, publish completion report, enter HALT.

---

# Phase 5 Extension — Local Night-Run Intake (Deterministic Test Mode)

## Objective

Implement a minimal local issue intake system for night-run testing.

No Gitea.
No multi-user separation.
No external dependencies.

This is a deterministic kernel-level integration test only.

## Execution Plan (Phase 5 Extension)

- [x] Step 1: Add deterministic local intake source from `state/issues/open/*.md` and `*.json`.
- [x] Step 2: Define explicit local issue schema requirements with fail-closed validation (no implicit defaults).
- [x] Step 3: Integrate local intake mode in night-run with strict deterministic ordering.
- [x] Step 4: Process local issues sequentially and re-check queue after each completed issue.
- [x] Step 5: Add explicit local capability registry load from `state/capabilities/enabled.json`.
- [x] Step 6: Enforce no implicit capability grants in local mode.
- [x] Step 7: Emit capability request artifacts to `state/capability_requests/` on missing capability.
- [x] Step 8: Deny execution on missing capability with deterministic reason code (no fallback).
- [x] Step 9: Add positive test: hello-world local issue creates `helloworld.txt` via governed flow.
- [x] Step 10: Add negative test: email capability missing -> request artifact + deny.
- [x] Step 11: Add completion test: queue empty after processing -> deterministic HALT.
- [x] Step 12: Run full `pytest -q`, update roadmap/progress with evidence, and enter HALT.

## Exit Condition

Phase 5 Extension is complete only if:

- [x] Local issue intake works deterministically.
- [x] Capability request system enforced.
- [x] No silent privilege escalation possible.
- [x] Full test suite green.
- [x] HALT entered.

---

# Promotion Log

## Phase 1 → Phase 2
Approved by: ____________________  Don
Date: ____________________  27-02-2026

## Phase 2 → Phase 3
Approved by: ____________________  Don
Date: ____________________  27-02-2026

## Phase 3 → Phase 4
Approved by: ____________________  Don
Date: ____________________  27-02-2026

---

End of Roadmap.

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

All improvements must be:

Auditable

Deterministic

Fail-closed

Budget-accounted

Boundary-enforced

## Tasks

### 4.1 Improvement Proposal Pipeline (PR-Only)
Objective

All self-improvements must flow through a governed PR process.

Tasks

 Add canonical proposal template: docs/specs/self_improvement_proposal.v0.1.md

Problem statement

Risk tier (LOW / MED / HIGH)

Affected components

Determinism impact

Test plan (mandatory)

Rollback strategy

 Require PR checklist for self-improvement changes.

 Tag PRs with self-improvement label.

 Require supervisor approval before merge.

Validation Criteria

 No self-improvement merged without proposal template.

 Proposal includes explicit risk tier.

 Proposal includes deterministic test plan.

 Full pytest suite passes before merge.

### 4.2 Allowed Change Boundary (Hard Constraints)
Objective

Prevent self-improvement from mutating governance authority.

Tasks

 Define allowlist for self-improvement changes:

✅ docs/

✅ tests/

✅ Explicit runtime modules (if declared in proposal)

❌ Governance core (unless HIGH-risk + token)

 Add static boundary scan test for PR validation.

 Fail-closed if disallowed files modified.

Validation Criteria

 Disallowed path modification → denied.

 Direct governance-core edits without HIGH-tier → rejected.

 All runtime changes include test updates.

### 4.3 Risk Classification & Approval Tokens (Tiered Control)
Objective

Improvements must be classified and gated by risk.

Risk Tiers

LOW — Docs/tests only, no runtime change.

MED — Refactor preserving behavior.

HIGH — Scheduler, budget, governance, approval tokens, phase acceptance, integrity.

Tasks

 Define canonical risk-tier specification document.

 Require approval token for HIGH-risk changes.

 Require golden-determinism evidence for MED/HIGH.

 Log tier classification in audit record.

Validation Criteria

 HIGH-risk without token → denied.

 MED/HIGH without determinism evidence → denied.

 Audit log contains tier + decision.

### 4.4 Determinism Guardrails (Golden Evidence)
Objective

Ensure improvements preserve deterministic behavior.

Tasks

 Define determinism_evidence.json schema.

 Add identical-input → identical-output validation tests.

 Ensure no uncontrolled timestamps introduced.

 Require rerun consistency tests for runtime changes.

Validation Criteria

 Identical state produces identical artifacts.

 No wall-clock dependency in governance logic.

 Determinism evidence included in PR.

### 4.5 Budget Accounting for Improvements
Objective

Self-improvement consumes autonomy budget.

Tasks

 Introduce improvement budget category.

 Record PR ID + tier in audit.

 Deny improvement if budget exhausted.

 Fail-closed on corrupt budget state.

Validation Criteria

 Improvement without budget → denied.

 Budget consumption deterministic and logged.

 Corrupt state → fixed deny code.

### 4.6 No Mutation Outside Governed Execution
Objective

Prevent direct runtime mutation outside PR workflow.

Tasks

 Enforce PR-only mutation rule.

 Add test detecting direct write attempts.

 Fail-closed on unauthorized mutation path.

Validation Criteria

 Direct mutation attempt → denied + audit.

 Only governed workflow may modify runtime logic.

### 4.7 Integration with Phase Acceptance Rule
Objective

Self-improvement merges require phase acceptance verification.

Tasks

 Require phase-acceptance verify before merge.

 Evidence must include:

Full suite result (0 failed)

Skip justifications

Roadmap update

Progress update

HALT state

 Add negative tests for missing evidence.

Validation Criteria

 Merge denied without acceptance evidence.

 Full suite must be green.

 Skips explicitly justified.

### 4.8 HALT Discipline for Self-Improvement
Objective

Prevent continuous self-expansion.

Tasks

 Enforce “HALT after PR creation” rule.

 Require explicit authorization to implement beyond proposal.

 Log awaiting-approval state.

Validation Criteria

 No commits beyond proposal without authorization.

 HALT state recorded after proposal.

## Validation Criteria

Phase 4 Exit Condition

Phase 4 is complete only if:

 All self-improvement flows via governed PR.

 Risk tiers enforced.

 Approval tokens integrated for HIGH-risk.

 Determinism preserved.

 Budget accounted.

 Phase acceptance verify integrated.

 No red tests.

 HALT discipline respected.

---

# Promotion Log

## Phase 1 → Phase 2
Approved by: ____________________  Don
Date: ____________________  27-02-2026

## Phase 2 → Phase 3
Approved by: ____________________  Don
Date: ____________________  27-02-2026

## Phase 3 → Phase 4
Approved by: ____________________  
Date: ____________________  

---

End of Roadmap.

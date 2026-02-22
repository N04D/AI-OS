Phase-Gate Governance Protocol v0.1
Purpose

This specification defines the deterministic phase-gating mechanism that controls
when the Supervisor is allowed to execute build tasks from each architectural phase.

The goal is to ensure:

architectural order is enforced

unsafe forward execution is impossible

autonomy emerges phase-by-phase, not chaotically

No autonomous execution beyond the active phase is permitted.

Architectural Context

Execution hierarchy becomes:

Phase Registry
→ Active Phase Resolution
→ Issue Eligibility Filter
→ Governed Execution
→ Phase Completion Evaluation
→ Deterministic Phase Advancement

This converts the repository into a finite-state machine for autonomy.

Core Principles
1. Single Active Phase

At any moment:

exactly one phase is active

all later phases are execution-blocked

earlier phases are immutable history

Failure classification:

governance.phase.invalid

2. Deterministic Issue Eligibility

Supervisor MAY execute an issue only if:

label includes type:build

milestone equals active phase

issue is NOT labeled in-progress

governance validation passes

environment validation passes

Otherwise execution MUST be skipped.

Failure classification:

governance.phase.blocked

3. Phase Completion Rule

A phase is complete when:

all type:build issues in that milestone are:

state = closed

governed commit present

execution verified = true

Completion MUST be computed via API, not memory.

Failure classification:

governance.phase.incomplete

4. Deterministic Phase Advancement

When a phase becomes complete:

Supervisor MUST:

log phase completion event

advance active phase to next numerical phase

emit governance compliance report

begin execution loop for new phase

Advancement MUST be:

atomic

logged

irreversible

Failure classification:

governance.phase.advance_failed

5. Hard Stop at Final Phase

If Phase 5 completes:

Supervisor MUST:

stop autonomous execution

emit final autonomy-completion report

enter passive monitoring mode

No further execution allowed.

Failure classification:

governance.autonomy.overflow

Phase Registry Contract

Canonical ordered phases:

Phase 1 — Governed Core Runtime

Phase 2 — Environment Validation Layer

Phase 3 — Task Execution Engine

Phase 4 — Result & State Management

Phase 5 — End-to-End Governed Autonomy

Ordering MUST be deterministic and immutable.

Active Phase Storage

Active phase MUST be derived from:

repository milestone state
OR

deterministic state file:

agents/state/active_phase.json


Format:

{
  "active_phase": 1,
  "updated_at": "UTC ISO8601"
}


State drift between file and repository is a violation.

Failure classification:

governance.phase.state_drift

Supervisor Enforcement Logic

Before selecting a task, Supervisor MUST:

resolve active phase

filter issues strictly within that phase

verify phase not complete

proceed with governed execution

If phase complete → trigger deterministic advancement.

Logging Requirements

Supervisor MUST append to:

logs/phase_governance.log


Each entry:

{
  "timestamp": "UTC ISO8601",
  "active_phase": 2,
  "event": "phase_completed | phase_advanced | execution_blocked",
  "details": {}
}


Logs MUST be append-only and deterministic.

Determinism Guarantees

Given identical:

repository state

milestones

labels

closed issues

Phase resolution MUST produce identical:

active phase

eligible task set

advancement timing

Non-determinism is forbidden.

Failure classification:

governance.phase.nondeterministic

Security Model

Phase-gating prevents:

premature autonomous behavior

execution of incomplete architecture

uncontrolled recursive task generation

This is the primary safety boundary of the AI engineering system.

Acceptance Criteria

Protocol is valid when:

Supervisor refuses to run Phase 3 while Phase 2 incomplete

Supervisor advances automatically after last Phase-N build closes

Advancement logged deterministically

Phase 5 completion halts execution

Status

Version: v0.1
State: Canonical after commit
Next Spec:
Autonomous Phase Completion Evaluation Spec v0.1

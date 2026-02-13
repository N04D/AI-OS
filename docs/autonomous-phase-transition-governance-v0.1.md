Autonomous Phase Transition Governance Spec v0.1
Purpose

This specification defines the governed rules for automatic phase transitions
inside the deterministic multi-cycle scheduler.

The previous spec introduced:

continuous autonomous execution

This spec guarantees:

safe, deterministic, and auditable promotion between phases

without human intervention.

Scope

Modify only:

supervisor/supervisor.py


Do not:

change scheduler timing

modify executor/orchestrator behavior

introduce parallelism

alter governance enforcement rules

This spec is limited strictly to:

phase completion detection

promotion authorization

promotion logging

terminal autonomy handling

Core Principle

A phase transition is not a scheduling event.

It is a governance decision.

Therefore:

A phase may advance only when governance conditions are satisfied.

Deterministic Phase Completion Rule

A phase is considered complete only if:

ALL conditions are true:


No remaining open issues in the active phase with:

label type:build

state open

No issue in the phase contains:

label in-progress

The last executed task in the phase finished with:

execution_verified = true

task_final_state = completed

governed commit (if changes existed)

Promotion Algorithm

When a cycle ends:

if phase_complete(active_phase):
    promote_to_next_phase()
else:
    remain_in_current_phase()

Promotion Must Be

single-step only

strictly sequential

non-skippable

Illegal behavior:

jumping multiple phases

re-opening previous phases

promoting during a failed cycle

Required Runtime Markers

The supervisor must emit deterministic markers:

When phase completes
PHASE_COMPLETE phase="<name>" milestone_id=<id>

When promotion occurs
PHASE_PROMOTED from="<phase>" to="<phase>"

When no further phases exist
AUTONOMY_COMPLETE
AUTONOMY_IDLE no_remaining_phases=true


These markers are mandatory for audit replay.

Safety Constraints

The supervisor must never:

promote during execution failure

promote if any in-progress label exists

promote without deterministic verification

terminate after final phase

Final phase behavior:

remain alive
enter deterministic idle loop

Determinism Requirements

Two identical repositories and issue states must produce:

identical phase completion moments

identical promotion order

identical runtime markers

Only timestamps may differ.

Acceptance Criteria

Implementation is valid only if:

Phase Governance Proof

Running the supervisor across all phases must show:

sequential completion of Phase 1 → Phase N

correct PHASE_COMPLETE markers

correct PHASE_PROMOTED markers

final AUTONOMY_IDLE state

Failure Protection Proof

If a task in a phase fails:

no promotion occurs

supervisor remains in same phase

retry cycle continues deterministically

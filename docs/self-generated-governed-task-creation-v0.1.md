Self-Generated Governed Task Creation Spec v0.1
Purpose

This specification introduces the first controlled form of autonomy:

the system may create its own tasks
but only inside strict governance boundaries.

The goal is to evolve from:

executing predefined work

to:

deterministically generating governed work.

Scope

Modify only:

supervisor/supervisor.py


Do not modify:

executor

orchestrator

governance enforcement core

scheduler timing

phase-gate logic

This spec adds one capability only:

governed self-generated task creation when a phase has no remaining work.

Activation Condition

Self-generated tasks are allowed only when:

ALL conditions are true:


Active phase is final phase

Phase 5 — End-to-End Governed Autonomy


No eligible type:build issues remain.

Phase transition governance reports:

AUTONOMY_IDLE no_remaining_phases=true


Only then may the supervisor create work.

Governance Boundary

Self-generated tasks must:

remain inside repository scope

reference existing specs or architecture

be deterministic and auditable

include clear expected outcome

Forbidden:

vague improvement ideas

speculative research

external network goals

self-modifying governance rules

Deterministic Task Template

Every generated issue must follow exact structure:

Title
auto: governed improvement task <N>


Where <N> is a monotonic deterministic counter.

Labels

Must include:

type:build
governed
deterministic
auto-generated

Body Structure (exact fields)
Origin: autonomous supervisor
Reason: no remaining governed build tasks in final phase
Scope: repository-internal deterministic improvement
Expected Outcome: concrete verifiable change
Governance: must pass commit-policy + phase-gate


No extra text allowed.

Creation Algorithm

When autonomy is active:

if no eligible build tasks:
    create exactly ONE new governed issue
    sleep deterministic interval
    continue normal execution loop

Hard Limits

One issue per cycle maximum

No burst creation

No parallel generation

Deterministic Counter Source

The task counter <N> must be derived from:

highest existing auto-generated issue number + 1


This guarantees:

replayable numbering

no randomness

no collisions

Required Runtime Markers

Supervisor must emit:

When autonomy activates
AUTONOMY_MODE_ACTIVE phase="Phase 5 — End-to-End Governed Autonomy"

When task is generated
AUTO_TASK_CREATED issue=<number> counter=<N>

When autonomy sleeps
AUTONOMY_SLEEP interval_seconds=<fixed>


Markers are required for audit determinism.

Safety Constraints

The system must never:

generate tasks outside final phase

generate tasks if any build issue exists

generate more than one task per cycle

bypass governance commit validation

Violation must trigger:

governance violation → abort cycle

Determinism Requirements

Two identical repositories must produce:

identical task numbers

identical creation timing (per cycle)

identical runtime markers

Only timestamps may differ.

Acceptance Criteria

Implementation is valid only if:

Autonomous Creation Proof

Running supervisor in final phase with no tasks must show:

AUTONOMY_MODE_ACTIVE
AUTO_TASK_CREATED issue=X counter=1


followed by normal governed execution of that task.

Non-Final Phase Protection

If run in any earlier phase:

NO auto task creation occurs


must be provable from logs.


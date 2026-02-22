Phase-Gate Multi-Cycle Scheduler Spec v0.1
Purpose

This specification introduces a deterministic multi-cycle execution scheduler on top of the existing phase-gate runtime.

The current supervisor can:

execute governed tasks

enforce phase-gate ordering

complete a single governed execution run

However, it cannot yet operate as a continuous autonomous system.

This spec upgrades the supervisor from:

single governed execution → permanent governed autonomy

Scope

Modify only:

supervisor/supervisor.py


Do not:

create new modules

refactor architecture

change governance rules

modify executor, orchestrator, or environment layers

This spec is strictly limited to:

scheduler loop behavior

cycle state management

deterministic phase advancement

Core Concept
Execution Cycle

A new deterministic runtime unit is defined:

CYCLE
 ├─ detect active phase
 ├─ select exactly ONE eligible task
 ├─ execute governed pipeline
 ├─ verify + commit + close
 ├─ re-evaluate phase completion
 └─ sleep → next cycle


Key invariant:

Exactly one task per cycle
This preserves determinism and auditability.

Continuous Supervisor Loop
Current Behavior
run once → exit

Required Behavior
while True:
    run governed cycle
    sleep deterministic interval


Define constant:

DEFAULT_CYCLE_INTERVAL_SECONDS = 30


Rules:

must be constant

must not depend on runtime duration

must not vary dynamically

This guarantees repeatable execution timing.

Phase Advancement

After each completed cycle:

if phase_complete:
    advance_to_next_phase()


Important constraints:

supervisor must NOT exit

next cycle must detect the new active phase

phase ordering must remain strictly sequential

Terminal Condition

If no remaining phases exist:

print("AUTONOMY_COMPLETE")
enter governed idle loop


The supervisor:

must not terminate

must remain alive in deterministic idle state

Determinism Requirements

The scheduler must never:

execute more than one task per cycle

run tasks in parallel

use dynamic sleep timing

skip phases

exit without governance cause

All runtime behavior must be:

fully replayable from logs.

Required Runtime Markers

The supervisor must emit the following structured markers:

CYCLE_START id=<n>
CYCLE_END id=<n> status=<completed|idle>
PHASE_ADVANCED from="<phase>" to="<phase>"
AUTONOMY_IDLE no_remaining_phases=true


These markers are mandatory for:

audit replay

deterministic verification

future autonomous self-evaluation agents

Acceptance Criteria

Implementation is valid only if all conditions hold.

Runtime Proof

When running the supervisor:

at least 3 consecutive cycles must execute

exactly 1 task per cycle

correct phase advancement must occur

system must reach idle state without crashing

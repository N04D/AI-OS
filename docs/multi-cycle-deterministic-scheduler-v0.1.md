Spec: Multi-Cycle Deterministic Scheduler v0.1

File: docs/multi-cycle-deterministic-scheduler-v0.1.md

Purpose

This specification defines the deterministic scheduling layer that enables the Supervisor to run continuous governed execution cycles safely and predictably.

It standardizes:

cycle timing

bounded retries

failure semantics

backoff rules

state persistence

multi-agent dispatch pacing

No autonomous operation beyond a single cycle is allowed unless this scheduler is implemented.

Goals

The Scheduler MUST guarantee:

Deterministic runtime behavior

Bounded execution time per cycle

No runaway loops

Reproducible decision-making

Safe retry behavior

Persistent state to survive restarts

Non-Goals

The Scheduler MUST NOT:

implement task execution logic itself

make architectural decisions

introduce new governance rules

replace the GovernanceEnforcer

create “AI planning” behavior beyond deterministic selection rules

Terminology

Cycle: One full Supervisor iteration from startup checks → decision → action → report → sleep.

Governed Execution Cycle: A cycle that passes governance gates and environment validation gates.

Dispatch: Hand-off to an external executor (e.g., Codex) for implementation.

Backoff: Deterministic delay applied after failures.

State Store: Persistent file used to track cycle counters, last task, failures, etc.

Scheduler Position in Runtime

Execution order MUST be:

Supervisor Start

Governance Context Load

Governance Validation

Environment Validation

Scheduler Cycle Start

Task Selection

Pre-Dispatch Governance Gate

Claim Task

Dispatch Task (optional; future)

Compliance Report

Scheduler Sleep

Next cycle

Deterministic Cycle Contract
Cycle Frequency

Default cycle interval MUST be 60 seconds

The scheduler MUST support a configuration value:

{
  "cycle_interval_seconds": 60
}


If missing, default to 60.

Bounded Runtime Per Cycle

A cycle MUST have a hard maximum runtime:

cycle_max_runtime_seconds = 90 (default)

If exceeded:

the cycle MUST abort

report MUST include failure code

scheduler MUST sleep with deterministic backoff

proceed to next cycle

Config key:

{
  "cycle_max_runtime_seconds": 90
}

Persistent Scheduler State

The scheduler MUST persist state to:

File: agents/state/scheduler_state.json

State MUST include:

{
  "cycle_count": 0,
  "last_cycle_utc": "ISO8601",
  "last_selected_issue": null,
  "last_claimed_issue": null,
  "consecutive_failures": 0,
  "last_failure_code": null,
  "backoff_seconds": 60
}

State Rules

MUST be written at end of every cycle (success or failure)

MUST be readable at startup

MUST be created automatically if missing

MUST be treated as authoritative over chat memory

Deterministic Backoff

Backoff MUST be deterministic and bounded.

Backoff Function

On failure:

consecutive_failures += 1

backoff_seconds = min(60 * consecutive_failures, 600)

So:

1 failure → 60s

2 failures → 120s

…

capped at 600s (10 min)

On success:

consecutive_failures = 0

backoff_seconds = cycle_interval_seconds

Failure Definition

A cycle is considered “failed” if ANY of the following occurs:

governance validation fails

environment validation fails

task claim fails

cycle runtime exceeded

unhandled exception

Failure Codes

Scheduler MUST emit one of these failure codes:

scheduler.governance_failed

scheduler.environment_failed

scheduler.no_tasks

scheduler.claim_failed

scheduler.runtime_exceeded

scheduler.exception

Task Selection Rules

The scheduler MUST NOT implement “priority AI”.

It MUST use deterministic selection only:

fetch open issues

filter issues not labeled in-progress

select the lowest issue number

If no selectable issues:

failure code MUST be scheduler.no_tasks

cycle is NOT considered “failure” for backoff escalation (special rule)

scheduler sleeps cycle_interval_seconds

Task Claim Rules

Claim step MUST be atomic and deterministic:

add label "in-progress" to selected issue

verify label exists afterward via read-back

if verification fails → scheduler.claim_failed

Output Requirements

Each cycle MUST print:

cycle start line

state summary line

validation results summary

task selection summary

claim status

compliance report block

scheduler sleep duration

Example:

CYCLE_START count=12 ts=2026-02-13T10:00:00Z
STATE failures=0 backoff=60s last_claimed=1
ENV_VALID=true
TASK_SELECTED #14 "fix: ..."
CLAIMED #14 label=in-progress verified=true
<governance compliance block>
SLEEP seconds=60

Governance Compatibility Requirements

Scheduler MUST integrate with GovernanceEnforcer:

MUST load context before cycle begins

MUST enforce immutability on every cycle

MUST emit compliance report every cycle

If governance fails:

scheduler MUST not proceed to claiming

MUST log violation

MUST backoff deterministically

Implementation Constraints

MUST be implemented using Python standard library only

MUST not introduce new services

MUST not require human interaction

MUST not require network access beyond configured Gitea API base

MUST not modify governance files

Acceptance Criteria

Implementation is complete when:

Supervisor runs indefinitely using scheduler loop

Scheduler persists state in agents/state/scheduler_state.json

Backoff works and is capped

Runtime per cycle is bounded

No-task cycles do not escalate backoff

Cycle output format includes required lines

Claim step is verified

Compliance report prints each cycle

Next Spec Dependency

Once this spec is implemented, the next spec may define:

Executor dispatch interface (Codex invocation contract)

Result ingestion & issue closing protocol

Failure recovery semantics per task

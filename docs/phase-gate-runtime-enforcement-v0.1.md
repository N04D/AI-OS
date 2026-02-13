Phase-Gate Runtime Enforcement Spec v0.1
Purpose

This specification defines the runtime enforcement layer that prevents governed autonomy from stalling in in-progress and ensures deterministic phase progression.

It introduces Phase-Gate runtime logic into the existing Supervisor loop so that:

in-progress is treated as a lock with ownership and TTL

tasks are deterministically completed/closed after verified execution + governed commit

phases (milestones) deterministically unlock only when all phase issues are complete

the supervisor never keeps the repository in a “claimed forever” state

This spec is runtime-only: it defines behavior and minimal wiring, not a new framework.

Scope
In scope

Modify ONLY:

supervisor/supervisor.py

(optionally) one small helper module supervisor/phase_gate.py IF it is purely functional and does not add architecture

Enforce:

deterministic claim lifecycle

deterministic release/cleanup

deterministic phase completion rules

Out of scope

Agent identity / SSH key separation (separate spec)

Multi-node scheduling (separate spec)

Planning/spec generation (separate spec)

Refactors, new frameworks, major re-architecture

Definitions
Phase

A “Phase” is a Milestone in the repo, named exactly:

Phase 1 — Governed Core Runtime

Phase 2 — Environment Validation Layer

Phase 3 — Task Execution Engine

Phase 4 — Result & State Management

Phase 5 — End-to-End Governed Autonomy

Phase-Gate

A Phase-Gate is the rule set:

The system MUST NOT execute issues from Phase N+1 if Phase N still has open type:build issues.

Claimed task

An issue with label in-progress.

Stuck claim

An issue labeled in-progress without a valid claim heartbeat or beyond TTL.

Governance Requirements

Must run under Governance Contract v0.1

Must remain deterministic

Must not introduce nondeterministic timing behavior beyond fixed bounded waits

Must not commit unrelated files

Must not mutate governance contract files

Runtime Behavior
1) Phase eligibility gate (pre-dispatch)

Before selecting any issue:

Supervisor MUST list milestones and determine the earliest phase milestone that still contains open type:build issues.

Supervisor MUST restrict eligible issues to:

type:build

governed

deterministic

NOT in-progress

milestone == current active phase (earliest incomplete phase)

If no eligible issues exist in the active phase:

Supervisor MUST emit:

PHASE_GATE_NO_ELIGIBLE_ISSUES phase=<name>

Supervisor MUST sleep deterministically (60s) and retry.

2) Claim lifecycle enforcement

When claiming an issue:

Supervisor MUST apply in-progress

Supervisor MUST write a deterministic claim comment containing:

CLAIMED_BY=<supervisor_instance_id>

CLAIMED_AT=<UTC_ISO>

GOV_HASH=<first12>

CLAIM_TTL_SECONDS=<int>

CLAIM_VERSION=v0.1

This comment is the canonical claim proof.

Supervisor MUST then immediately verify label presence via API:

If missing: abort cycle deterministically.

3) TTL-based stuck-claim cleanup

At startup of each loop iteration (before selecting a new issue), Supervisor MUST:

Query open issues with in-progress

For each such issue, fetch latest claim comment

If:

CLAIMED_AT missing, OR

CLAIMED_AT + TTL < now
then issue is stuck

For stuck issues:

Supervisor MUST remove in-progress

Supervisor MUST comment:

UNCLAIMED_STUCK ttl_expired=true

include previous claim metadata if present

Constraints:

TTL MUST be constant: 3600 seconds

Supervisor MUST only remove stuck claims if it can prove staleness deterministically.

4) Completion criteria (post-execution)

After execution + verification:

An issue may only be closed if ALL are true:

execution_dispatched == true

execution_verified == true

result.status == success

result.tests_passed == true

governed commit created == true OR changed_files == [] (no-op execution)

If changed_files == []:

Supervisor MUST allow closure without commit

Supervisor MUST comment:

NOOP_EXECUTION verified=true changed_files=0

If commit is required but not created:

Supervisor MUST keep issue open

Supervisor MUST remove in-progress (release lock)

Supervisor MUST comment:

EXECUTION_VERIFIED_BUT_COMMIT_MISSING retryable=true

5) Closing behavior

On closure:

Supervisor MUST:

close the issue via API

remove in-progress

post final comment:

COMPLETED phase=<phase_name>

COMMIT=<hash|none>

VERIFIED=true

DISPATCH_TIMESTAMP=<UTC>

FINAL_STATE=completed

6) Phase completion detector

After closing an issue (same loop), Supervisor MUST check:

Are there any remaining open type:build issues in the current phase milestone?

If none remain:

Supervisor MUST emit:

PHASE_COMPLETE phase=<name>

Supervisor MUST comment on the Phase-Gate issue (or create one deterministic event comment) stating:

PHASE_GATE_UNLOCK next_phase=<name|none>

Supervisor MUST NOT auto-create new issues here (planning is separate spec).
This spec only requires detection + reporting.

Deterministic Output Contracts
Required console output lines

Supervisor MUST print these machine-grepable lines:

PHASE_GATE_ACTIVE phase="<name>" milestone_id=<id>

PHASE_GATE_ELIGIBLE_COUNT n=<int>

CLAIM_APPLIED issue=<n>

CLAIM_VERIFIED issue=<n> in_progress_present=true|false

CLAIM_STUCK_RELEASED issue=<n>

TASK_COMPLETED issue=<n> commit=<hash|none>

PHASE_COMPLETE phase="<name>"

Failure Codes (classification)

Failures MUST map to one of:

phase_gate.milestones.unavailable

phase_gate.active_phase.undetermined

phase_gate.claim.failed

phase_gate.claim.stuck_cleanup.failed

phase_gate.close.failed

phase_gate.commit.required_missing

phase_gate.execution.verification_failed

Each failure MUST:

abort the cycle

emit compliance report block

sleep deterministic interval (60s)

Acceptance Tests
Test A — Stuck in-progress cleanup

Manually label an open issue in-progress

Ensure claim comment is absent or old (>3600s)

Run supervisor once
Expected:

CLAIM_STUCK_RELEASED issue=<n>

label removed

issue remains open

Test B — Phase gating works

Put an open type:build issue in Phase 1

Put an open type:build issue in Phase 2

Run supervisor
Expected:

selects only Phase 1 issue

prints PHASE_GATE_ACTIVE phase="Phase 1 — ..."

Test C — Completion clears in-progress

Run a build issue through execution
Expected:

issue closed

in-progress removed

comment contains COMPLETED ...

Implementation Notes (non-binding)

Prefer using existing API request helper in supervisor/supervisor.py

TTL parsing must be strict (UTC ISO8601 only)

If multiple claim comments exist, use the latest one

Non-Goals

This spec does not solve identity separation

This spec does not create planning issues

This spec does not introduce new agent roles

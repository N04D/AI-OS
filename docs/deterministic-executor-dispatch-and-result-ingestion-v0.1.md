Deterministic Executor Dispatch & Result Ingestion Spec v0.1
Purpose

This document defines the mandatory deterministic mechanism by which the Supervisor:

dispatches a claimed task to the BUILDER agent

validates execution results

ingests outcomes into the governed system state

finalizes task completion in a verifiable and auditable way

This specification forms the final bridge between governance and real execution.

No governed task lifecycle may complete without passing through this executor dispatch and ingestion protocol.

Architectural Position

Execution order becomes:

Supervisor Start
→ Governance Context Load
→ Governance Validation
→ Environment Validation
→ Task Claim
→ Executor Dispatch ← NEW LAYER
→ Result Ingestion & Verification ← NEW LAYER
→ Compliance Report
→ Cycle Continuation

This enables:

governed execution

deterministic completion

auditable task closure

Core Principles
1. Deterministic Dispatch

The Supervisor MUST dispatch tasks to the BUILDER agent using:

explicit instruction text derived from the claimed issue

immutable governance-validated context

bounded execution expectations

Dispatch MUST:

occur exactly once per claimed task

include no ambiguity or optional language

be fully reproducible from repository state

Failure classification:

execution.dispatch.invalid
execution.dispatch.nondeterministic

2. Single Active Executor

At any time:

only one execution process may run for a claimed issue

concurrent execution of the same issue is forbidden

Supervisor MUST enforce:

atomic claim ownership

execution lock semantics

Failure classification:

execution.lock.violation

3. Bounded Execution Contract

Executor runtime MUST:

start within deterministic timeout

complete or fail within bounded duration

emit structured output

Unbounded or hanging execution is forbidden.

Failure classification:

execution.timeout
execution.no_output

4. Immutable Instruction Scope

The BUILDER agent MUST:

operate only within files explicitly allowed by the task

avoid architectural drift

follow Governance Contract v0.1

Any deviation MUST be treated as:

execution.scope.violation

Executor Dispatch Protocol
Required Dispatch Inputs

Supervisor MUST provide:

{
  "task_id": <issue number>,
  "instruction": "<deterministic instruction text>",
  "allowed_files": [...],
  "expected_outcome": "<verifiable result>",
  "governance_hash": "<sha256>",
  "timestamp": "<UTC ISO8601>"
}


Dispatch without all required fields is invalid.

Failure classification:

execution.dispatch.malformed

Dispatch Mechanism

Dispatch MAY occur via:

CLI invocation

local agent runtime

controlled subprocess

BUT MUST satisfy:

deterministic invocation command

captured stdout/stderr

captured exit code

Result Ingestion Protocol
Required Executor Output

Executor MUST return structured result:

{
  "status": "success" | "failure",
  "changed_files": [...],
  "commit_hash": "<optional>",
  "tests_passed": true | false,
  "logs": "...",
  "timestamp": "<UTC ISO8601>"
}


Missing fields → invalid execution.

Failure classification:

execution.result.invalid

Supervisor Verification Steps

Supervisor MUST verify:

execution status is deterministic

changed files ⊆ allowed files

commit message follows governance rules

no governance violations occurred

execution completed within timeout

If any check fails:

task MUST NOT be closed

violation MUST be logged

execution cycle MUST retry deterministically

Failure classification:

execution.verification.failed

Task Finalization Rules
Successful Completion

If verification passes:

Supervisor MUST:

close the issue

attach compliance summary

record execution metadata

Result state:

task.state = "completed"

Failed Execution

If execution fails:

Supervisor MUST:

keep issue open

attach failure report

schedule deterministic retry

Result state:

task.state = "retry_pending"

Compliance Reporting Extension

Compliance report MUST now include:

execution_dispatched: true | false
execution_verified: true | false
task_final_state: completed | retry_pending | blocked

Logging Requirements

Supervisor MUST log:

dispatch timestamp

executor command

exit status

verification outcome

final task state

Log classification:

logs/execution_cycle.log

Failure Escalation

If repeated execution failures exceed threshold:

Supervisor MUST transition task to:

task.state = "blocked"


AND emit governance-level alert.

Failure classification:

execution.escalation.blocked

Deterministic Guarantees

This layer guarantees:

no silent execution

no unverifiable completion

no uncontrolled agent behavior

This specification therefore establishes:

the first fully governed autonomous build-and-close loop.

Future Extensions

Planned evolutions:

multi-executor scheduling

distributed execution nodes

cryptographic result attestation

reproducible build verification

All extensions MUST remain compliant with:

Governance Contract v0.1

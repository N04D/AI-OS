Evaluation & Commit Protocol Spec v0.1
Purpose

This document defines the deterministic decision layer that evaluates execution results and governs whether repository state changes may be committed.

This protocol ensures that no autonomous code modification can occur without:

governance compliance

environment stability

deterministic execution success

commit policy validation

It is the final safety boundary before irreversible system change.

Architectural Position

The governed runtime becomes:

Supervisor
→ Governance Enforcement
→ Environment Validation
→ Task Claim
→ Task Execution Engine
→ Evaluation & Commit Protocol   ← THIS SPEC
→ Compliance Report
→ Sleep → Next Loop


This layer converts execution output into a binary governed decision:

commit
OR
reject


No intermediate state exists.

Evaluation Input Contract

The protocol receives the immutable execution result:

{
  "task_id": "",
  "exit_code": 0,
  "changed_files": [],
  "logs": "",
  "duration_seconds": 0,
  "builder_status": "success | failure | timeout"
}


This data MUST NOT be modified during evaluation.

Deterministic Evaluation Rules

Execution is considered valid only if ALL conditions hold:

exit_code == 0
AND builder_status == "success"
AND governance_compliant == true
AND environment_valid == true
AND expected_outcome satisfied


If any condition fails:

evaluation_result = "rejected"


No soft-fail or warning states are permitted.

Expected Outcome Verification

The protocol MUST verify the task-defined success condition.

Examples:

required file created

specific tests passing

issue state transition completed

label applied successfully

If outcome cannot be deterministically proven:

evaluation_result = "rejected"


Ambiguity is treated as failure.

Commit Policy Enforcement Gate

Before any commit:

The protocol MUST validate:

1. File Scope
changed_files ⊆ allowed_files


Unexpected modification ⇒ reject

2. Governance Integrity

The following files MUST remain unchanged:

docs/governance.md
docs/*spec*.md (unless task explicitly allows)
agents/state/environment.json


Violation ⇒ critical governance breach → reject

3. Commit Message Determinism

Commit message MUST follow:

type(scope): summary


Allowed types:

feat
fix
docs
chore


Invalid format ⇒ reject

4. Environment Drift Check

Immediately before commit:

Re-validate:

environment_valid == true
governance hash unchanged


Drift detected ⇒ reject

Commit Execution Rules

A commit MAY occur only when:

evaluation_result == "success"
AND commit_policy == "pass"


Then:

create commit
attach task_id reference
record timestamp
push to remote


All steps MUST be atomic.

If atomicity fails:

rollback
mark execution as failed

Rejection Semantics

When rejected:

The system MUST:

create structured rejection record
store execution artifacts
log rejection reason
DO NOT modify repository


Supervisor then:

continues next governed loop


No retry inside same cycle.

Structured Evaluation Result

The protocol MUST emit:

{
  "task_id": "",
  "evaluation_result": "success | rejected | failed",
  "commit_performed": true,
  "rejection_reason": null,
  "violations": [],
  "timestamp": "UTC ISO8601"
}


This becomes part of permanent governed memory.

Compliance Reporting Integration

The Supervisor compliance report MUST now include:

evaluation_result
commit_performed
violation_count


This guarantees full auditability of autonomy.

Failure States

Terminal evaluation states:

success
rejected
failed
timeout
governance_violation
environment_invalid
commit_error


All MUST be:

logged
traceable
machine-readable


No silent termination allowed.

Security Boundary

This protocol defines the final irreversible boundary.

Anything that bypasses this layer is:

non-governed mutation
→ strictly forbidden

Future Evolution

Planned roadmap:

v0.2 → signed commits + cryptographic traceability
v0.3 → multi-agent evaluation consensus
v0.4 → automatic rollback snapshots
v1.0 → self-governing autonomous engineering system


All revisions MUST follow Governance amendment procedures.

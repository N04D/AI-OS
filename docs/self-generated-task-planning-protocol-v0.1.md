Self-Generated Task Planning Protocol Spec v0.1
Purpose

This document defines the governed mechanism by which the autonomous AI engineering system may propose, validate, and create new tasks without direct human instruction.

Its purpose is to ensure that:

autonomy emerges in a controlled, auditable manner

all self-generated work remains governance-compliant

system evolution stays deterministic and reversible

No task may be self-generated outside this protocol.

Architectural Position

The governed execution loop becomes:

Supervisor
→ Governance Enforcement
→ Environment Validation
→ External Task Fetch
→ Task Execution (if available)

→ Self-Generated Task Planning   ← THIS SPEC
→ Evaluation & Commit Protocol
→ System Memory Recording
→ Compliance Report
→ Sleep → Next Cycle


Self-planning only activates when:

no valid external tasks are available

Activation Condition

Self-Generated Planning MAY run only if:

open_external_tasks == 0
environment_valid == true
governance_compliant == true
last_cycle_memory_recorded == true


If any condition fails:

self-planning is forbidden

Planning Scope (v0.1 Limits)

The system MAY propose tasks related to:

missing validation
test coverage gaps
governance enforcement gaps
logging/observability gaps
documentation inconsistencies
deterministic failure recovery


The system MUST NOT propose:

architectural rewrites
governance changes
security-sensitive behavior
infrastructure mutations
self-modifying code


These remain human-governed domains in v0.1.

Deterministic Planning Method

Self-planning MUST be based solely on:

repository state
system memory records
failure frequency
unresolved validation domains
missing specifications


Forbidden inputs:

randomness
external internet data
non-deterministic prompts
hidden state


Planning must be fully reproducible from the same repository + memory state.

Proposal Generation Contract

Each generated task MUST follow this structure:

{
  "title": "type(scope): concise deterministic objective",
  "reason": "governed justification based on memory or repo state",
  "evidence": ["file/path", "failure_code", "missing_spec"],
  "risk_level": "low",
  "governance_safe": true
}


If any field is missing:

proposal is invalid

Governance Pre-Validation

Before creating an issue, Supervisor MUST verify:

proposal within allowed scope
no governance rule conflict
risk_level == low
deterministic justification present


Failure → proposal discarded and logged in failure memory.

Issue Creation Rules

If validated, Supervisor MAY:

create exactly ONE new issue per idle cycle


Issue MUST contain:

Title
auto: <deterministic objective>

Body

Must include:

governed justification
evidence references
clear success condition
statement: "Self-generated under Self-Generated Task Planning Protocol v0.1"

Rate Limiting (Critical Safety)

Self-generation MUST obey:

max 1 issue per cycle
max 5 consecutive self-generated cycles


After limit:

planning disabled until human or external task appears


Prevents runaway autonomy.

Memory Recording

Each planning attempt MUST record:

{
  "planning_attempted": true,
  "issue_created": true | false,
  "rejection_reason": "",
  "timestamp": ""
}


Stored in:

/memory/evolution.jsonl

Failure Handling

If issue creation fails:

record failure
classify cause
retry next governed cycle


Never retry within the same cycle.

Human Override Boundary

Human-created issues ALWAYS take priority over:

self-generated issues


This preserves:

human governance supremacy in v0.1

Compliance Report Extension

Supervisor MUST now include:

self_planning_attempted: true | false
self_issue_created: true | false
self_planning_blocked_reason: ""


Ensuring transparent emergence of autonomy.

Security Boundary

Any attempt to:

bypass governance validation
create multiple issues per cycle
generate forbidden task types


is classified as:

critical governance violation
→ immediate halt

Evolution Roadmap
v0.2 → multi-proposal ranking
v0.3 → semantic failure clustering
v0.4 → autonomous milestone planning
v1.0 → fully self-directed governed AI engineering loop


All evolution remains governance-gated.

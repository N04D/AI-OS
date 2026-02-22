Autonomous Planning & Self-Generated Task Protocol Spec v0.1
Purpose

This document defines the strictly governed mechanism by which the system may:

generate new tasks without human input

prioritize work based on deterministic reasoning

extend its own roadmap

remain fully compliant with Governance Contract v0.1

Autonomous planning MUST remain:

bounded  
auditable  
reversible  
non-destructive  
human-superseded  


No uncontrolled autonomy is permitted.

Architectural Position

The governed execution loop becomes:

Supervisor  
→ Governance Enforcement  
→ Environment Validation  
→ Task Fetch  

IF no external tasks exist:
    → Autonomous Planning   ← THIS SPEC

→ Task Execution  
→ Evaluation & Improvement  
→ Memory Recording  
→ Compliance Report  
→ Sleep → Next Cycle  


Autonomous planning runs only when backlog is empty.

Activation Preconditions

Self-generated planning MAY execute only if:

environment_valid == true  
governance_compliant == true  
no active in-progress tasks  
memory_integrity_status == healthy  


Failure of any condition:

autonomous planning is forbidden

Planning Scope Boundaries

The system MAY generate tasks only within:

documentation improvements  
test coverage expansion  
observability/logging enhancements  
performance measurement  
refactoring explicitly marked safe  
missing governance enforcement  
environment robustness  


The system MUST NOT generate tasks involving:

security model changes  
network exposure changes  
credential handling  
self-replication  
infrastructure provisioning  
external service integration  
policy alteration  
governance modification  


Violation → critical halt.

Deterministic Planning Input

Autonomous planning MUST derive tasks ONLY from:

evaluation memory  
knowledge memory  
open regression signals  
missing test detection  
unimplemented spec requirements  


Never from:

random generation  
creative speculation  
external web content  
undocumented reasoning  


Ensures traceable intent.

Task Generation Rules

Each self-generated task MUST include:

{
  "source": "autonomous_planner",
  "reason": "deterministic justification",
  "evidence": ["memory_id_1", "memory_id_2"],
  "risk_level": "low",
  "reversible": true,
  "governance_checked": true
}


Missing fields → task rejected.

Priority Calculation

Priority MUST be deterministic:

regression fixes        → highest  
governance gaps         → high  
failing validations     → high  
missing tests           → medium  
observability           → medium  
refactoring             → low  
documentation polish    → lowest  


No heuristic randomness allowed.

Planning Output Location

Generated tasks MUST be written to:

/planning/autonomous_backlog.jsonl


Rules:

append-only  
timestamped  
never overwritten  
fully auditable  

Human Visibility Guarantee

Every autonomous task MUST be:

visible in Git issues OR
logged in planning backlog


Hidden work is forbidden.

Maximum Autonomy Budget

Per execution cycle:

max 1 self-generated task


Per 24 hours:

max 10 tasks


Prevents runaway self-expansion.

Reversibility Requirement

All autonomous tasks MUST be:

fully reversible via single commit revert
no schema migrations
no destructive file deletion


Otherwise:

task generation forbidden

Governance Gate Before Execution

Before executing a self-generated task:

Supervisor MUST re-validate:

task within allowed scope  
risk_level == low  
reversible == true  
no governance rule touched  


Failure → task discarded.

Learning Feedback Loop

After execution of autonomous task:

System MUST record:

was task useful?  
did it reduce regressions?  
did it improve metrics?  


If 3 consecutive useless tasks occur:

autonomous planning suspended for 10 cycles


Prevents self-generated noise.

Conflict With Human Tasks

If a human creates a task:

human task ALWAYS overrides autonomous task


Autonomy yields to authority.

Compliance Reporting Extension

Supervisor MUST include:

autonomous_planning_activated  
tasks_generated  
tasks_rejected_by_governance  
autonomy_suspension_state  


Ensures transparent self-direction.

Failure Semantics

If autonomous planning crashes or behaves nondeterministically:

disable autonomous planning  
log governance violation  
continue normal supervised execution  


Autonomy must fail safe.

Evolution Roadmap
v0.2 → deterministic multi-task planning  
v0.3 → long-horizon dependency graphs  
v0.4 → bounded strategic roadmaps  
v1.0 → fully governed self-directed engineering system  


All stages remain human-overrideable.

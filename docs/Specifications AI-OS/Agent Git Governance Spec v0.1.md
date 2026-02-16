
Status: Draft

Scope: Git workflow and branch governance for a multi-agent system (Gemini, Codex, Supervisor) requiring auditability, determinism, and controlled self-improvement.

Objective: Prevent uncontrolled mutation of protected branches and ensure that all system evolution is traceable, reviewable, testable, and reversible.

1. Core Principles
1.1 Auditability Over Speed
Every change must be traceable to:

Agent identity

Linked issue/task

Explicit diff scope

Tests or validation evidence

Review and approval

No anonymous or implicit mutations are permitted.

1.2 Self-Improvement Is Work, Never Authority
Agents may improve the system only through governed proposals:

Feature branches

Pull requests

Reviews

Explicit approval

Direct mutation of protected branches is prohibited.

1.3 Determinism and Reproducibility
The repository is the system of record:

A decision = PR discussion

A change = commit

Validation = tests/checks

Release = tagged merge

All system evolution must be reconstructable from Git history.

2. Roles and Permissions
2.1 Roles
Supervisor
Validates governance compliance

Labels and reviews pull requests

May not push directly to main

Agents (Gemini, Codex, others)
Work only on feature branches

Must open pull requests

Cannot push to protected branches

Human Owner
Final merge authority to main

May initiate emergency hotfix flows

2.2 Agent Identity Requirements
Each agent must have:

Unique git user.name

Unique git user.email

Dedicated SSH key or access token

Restricted permissions (no direct push to protected branches)

Reserved branch namespace

Without identity isolation, accountability collapses.

3. Branch Model
3.1 Protected Branches
main → Stable release branch

develop → Integration branch

Rules:

No direct pushes to main

No force pushes

PR required for merges

(Optional but recommended: develop is also PR-only.)

3.2 Feature Branch Naming Convention
Format:

agent/<agent_name>/<type>-<id>-<slug>
Examples:

agent/codex/feat-042-heartbeat-isolation
agent/gemini/fix-017-json-parse-error
agent/supervisor/chore-009-governance-refactor
Allowed types:

feat – new feature

fix – bug fix

chore – maintenance/refactor

docs – documentation

test – testing-only changes

Each branch corresponds to one issue/task.

4. Issue and Task Coupling
4.1 One Branch = One Task
Every feature branch must map to a single issue

Issue ID must appear in branch name and commits

4.2 Commit Message Convention
Format:

<type>(<scope>): <summary> [#<id>]

Why:
What:
Risk:
Tests:
Example:

fix(gateway): isolate heartbeat session [#42]

Why:
Main agent sessions conflicted with heartbeat websocket.

What:
Assigned dedicated sessionKey='heartbeat'.

Risk:
Low; isolated to session handling.

Tests:
Ran openclaw agent smoke test and gateway session unit tests.
5. Pull Request Governance
5.1 PR Targets
Feature branches → develop

Hotfix branches → main (emergency only)

5.2 Required PR Content
Every PR must include:

Context

Description of changes

Risk assessment (low/medium/high)

Test evidence

Rollback strategy

Linked issue

5.3 Merge Requirements
Merge to develop
At least one review (another agent or human)

Supervisor label: governed

Tests passing (or documented waiver)

Merge to main
Human approval required

Label: release-approved

Tag/version update (if applicable)

6. Validation and Checks
If CI exists, required checks:

Linting

Unit tests

Smoke test

Format validation

If CI does not exist:

PR must include:

Commands executed

Exit codes

Relevant output logs

No undocumented manual validation is allowed.

7. Multi-Agent Concurrency Rules
7.1 Subsystem Isolation
An agent may not maintain multiple active branches targeting the same subsystem simultaneously (e.g., supervisor/, executor/, cli/).

This reduces merge conflicts and ownership ambiguity.

7.2 High-Risk Path Locking
High-risk paths include:

supervisor/supervisor.py

Governance core

Executor runtime

Orchestrator commit logic

Environment validation

Rule:

If an agent modifies a high-risk path, the issue must contain:

LOCK:<path>
Other agents must not modify that path until the lock is released.

8. Hotfix Flow
8.1 When Allowed
Security issue

Broken main

Critical release-blocking defect

8.2 Procedure
Create branch:

hotfix/<id>-<slug>
PR → main

Minimal validation

Human approval

Merge

Cherry-pick to develop to prevent drift

9. Versioning and Releases
Recommended: Semantic Versioning

MAJOR.MINOR.PATCH
develop may move rapidly

main represents stable releases only

Releases must be tagged

10. Repository Structure Governance
10.1 State vs Code
Runtime state files must not mutate protected branches without explicit justification.

Examples:

state/

memory.md

Generated artifacts should be placed in:

generated/
artifacts/
Never commit runtime noise into core logic directories.

11. Definition of Done
A task is complete only when:

Branch naming is correct

Commits reference issue

PR template completed

Tests validated

Required reviews obtained

Correct merge target used

12. Minimal Repository Enforcement Settings
Recommended repository configuration:

Protect main and develop

Require PR for merge

Require at least one approval

Disallow force push

Enforce status checks (if CI exists)

Final Statement
This governance model ensures:

Controlled recursive self-improvement

Multi-agent accountability

Deterministic system evolution

Audit-ready history

Safe parallel feature development

The system may evolve.
It may not mutate itself without record.

If you want, I can next produce:

A minimal PR template markdown file

A Gitea configuration checklist

Or a stricter v0.2 including automated branch enforcement rules



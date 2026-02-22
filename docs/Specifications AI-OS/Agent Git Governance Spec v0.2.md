 Agent Git Governance Spec v0.2

**Stricter Deterministic Multi-Agent Enforcement Model**

**Status:** Draft
**Supersedes:** v0.1
**Objective:** Enforce deterministic, auditable, multi-agent system evolution with strict isolation, proposal-based mutation, and automated enforcement boundaries.

This version assumes:

* Multiple autonomous agents
* Recursive self-improvement capability
* Governance-critical subsystems
* Distributed execution nodes

---

# 1. Non-Negotiable Invariants

These are system laws. Violations invalidate the build.

1. No direct mutation of `main`.
2. No direct mutation of `develop`.
3. No force pushes to protected branches.
4. No unsigned commits from agents.
5. No merge without validation evidence.
6. No branch without linked issue.
7. No high-risk file change without lock ownership.
8. No self-approval of own PR.

---

# 2. Branch Topology (Strict Mode)

## 2.1 Protected Branches

| Branch    | Purpose            | Direct Push | PR Required | Human Required |
| --------- | ------------------ | ----------- | ----------- | -------------- |
| `main`    | Stable releases    | No          | Yes         | Yes            |
| `develop` | Integration branch | No          | Yes         | No*            |

*Human required only for high-risk or release PRs.

---

## 2.2 Mandatory Branch Naming

```
agent/<agent>/<type>/<issue-id>-<slug>
```

Example:

```
agent/codex/feat/042-heartbeat-isolation
agent/gemini/fix/017-json-parse
```

Branch creation without issue ID is rejected.

---

# 3. Cryptographic Identity Enforcement

Each agent must:

* Use dedicated SSH key
* Use signed commits (GPG or SSH signing)
* Have isolated Git config
* Be denied push access to protected branches

Unsigned commits = rejected by branch protection rule.

---

# 4. PR Governance Hard Requirements

A PR is invalid unless it contains:

* Linked issue reference
* Risk classification
* Subsystem declaration
* Test evidence block
* Rollback procedure
* Determinism impact statement

Mandatory template fields:

```
### Subsystem
### Risk Level
### Determinism Impact
### Lock Required?
### Tests Executed
### Rollback Plan
```

If any field is missing → PR cannot merge.

---

# 5. Deterministic Merge Rules

## 5.1 Review Separation Rule

An agent cannot approve:

* Its own PR
* Any PR modifying its own core subsystem

Minimum approvals:

* 1 other agent
* Supervisor validation
* Human approval if:

  * High-risk path touched
  * Version bump
  * Governance layer modified

---

# 6. High-Risk Path Enforcement

High-risk paths:

* `supervisor/`
* `governance/`
* `executor/`
* `orchestrator/`
* `environment/`
* Any config affecting identity, permissions, or execution loop

If touched:

1. Issue must contain `LOCK:<path>`
2. Only one active lock per path
3. Supervisor must explicitly confirm
4. Human approval mandatory

Lock release happens only after merge.

---

# 7. Concurrency Controls

## 7.1 One Active Feature Per Agent Per Subsystem

Agents may not:

* Open multiple active PRs targeting same subsystem
* Work in parallel on governance-critical code

This prevents non-deterministic evolution.

---

## 7.2 Integration Freeze Window

Before merging into `main`:

* `develop` must be frozen
* No new feature merges allowed
* Only bugfix PRs permitted
* Supervisor validates commit graph stability

---

# 8. CI / Validation Hardening

Required automated checks:

* Lint
* Unit tests
* Smoke test
* Dependency audit
* Determinism check (re-run execution with identical output)

If determinism fails → merge blocked.

---

# 9. Self-Improvement Escalation Protocol

If an agent proposes:

* Governance change
* Permission model update
* Supervisor logic change
* Execution loop mutation

Then:

1. Classified as `SYSTEM_EVOLUTION`
2. Requires:

   * 2 approvals (1 agent + 1 human)
   * Explicit diff impact summary
   * Regression risk statement
3. Must run extended validation

No silent self-mutation allowed.

---

# 10. Hotfix Hard Mode

Hotfix branches:

```
hotfix/<issue-id>-<slug>
```

Rules:

* Minimal diff scope
* Direct PR to `main`
* Mandatory human approval
* Immediate cherry-pick to `develop`
* Post-incident review issue required

---

# 11. Version Governance

Only Supervisor may:

* Propose version bump

Only Human may:

* Approve MAJOR bump

Minor/Patch bumps require:

* Change log entry
* Backward compatibility statement

---

# 12. Repository Structural Boundaries

## 12.1 State Isolation

Runtime data must never alter protected branches automatically.

Forbidden:

* Auto-commit from running agents to `main`
* Implicit state persistence into governance files

---

## 12.2 Generated Code Rules

Generated code:

* Must live in `generated/`
* Must not modify core logic directly
* Must include generation metadata header

---

# 13. Merge Audit Trail Requirements

After every merge:

* Commit graph must remain linear or explicitly documented
* No squashing without preserving authorship
* PR discussion retained permanently

---

# 14. Emergency Governance Override

Only Human Owner may:

* Disable branch protection
* Force revert
* Revoke agent credentials
* Reset compromised subsystem

Override must be documented in an issue titled:

```
GOVERNANCE_OVERRIDE_<date>
```

---

# 15. Enforcement Summary

v0.2 introduces:

* Signed commit enforcement
* Lock-based subsystem isolation
* Determinism validation
* Review separation guarantees
* Structured escalation for system evolution
* Freeze windows for release
* Cryptographic identity requirement

This transforms Git from a versioning tool into a governance boundary.

---

# Final Governance Assertion

The system may improve itself.

It may not:

* Approve itself,
* Mutate protected branches,
* Alter governance invisibly,
* Or bypass identity enforcement.

All evolution must be:

* Proposed
* Reviewed
* Validated
* Approved
* Auditable

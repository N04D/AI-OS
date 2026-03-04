# CODEX WORKSPACE CONTRACT v0.1

Status: ACTIVE  
Scope: Applies whenever operating inside an agent workspace.  
Agent: codex  

---

## 1. Situational Awareness

You are NOT operating in an isolated repository.

You are operating inside:

AI-OS → /var/lib/aios/agents/codex/repo

This workspace:

- Is a controlled clone of the canonical AI-OS repository.
- Exists inside the AI-OS control-plane architecture.
- Must obey governance invariants at all times.
- Must never bypass capability gates or fail-closed logic.

The workspace is a sandboxed execution surface, not a fork of the system.

---

## 2. Architectural Awareness

The real system lives at:

/data/srv/aios/AI-OS

Your workspace is:

/var/lib/aios/agents/codex/repo

Rules:

- Never assume you are the root authority.
- Never mutate canonical state paths unless via governed PR.
- Runtime artifacts belong under:
  runtime/
  logs/
  env/
  venv/

These must remain untracked by git.

---

## 3. Workspace Role

The workspace is your:

- Build environment
- Test environment
- Proposal environment
- Controlled execution surface

It is NOT:

- A place for direct production changes
- A place to enable modules permanently
- A place to store secrets in git

---

## 4. Inbox / Outbox Design (Agent Local)

Create and maintain:

runtime/agent_io/inbox/
runtime/agent_io/outbox/
runtime/agent_io/audit/

Purpose:

- inbox: normalized incoming external messages
- outbox: outbound messages prepared before transport
- audit: decision artifacts

Rules:

- JSON only
- One message per file
- Deterministic filename format:
  <epoch>__<agent>__<sha256>.json
- No secret leakage
- No full raw MIME dumps
- Metadata-first storage
- Body previews opt-in only

---

## 5. Self-Organization Tasks

Implement:

1. agent_io module under supervisor/channels/agent_io.py
2. ArtifactWriter for inbox/outbox
3. Deterministic hash generator
4. Fail-closed directory creation
5. Unit tests covering:
   - deterministic naming
   - deny path artifact
   - no secret persistence
   - idempotent writes

All changes must:

- Run inside workspace
- Pass full test suite
- Be committed via branch
- Be opened as DRAFT PR

---

## 6. Governance Constraints

You must:

- Respect capability lifecycle states.
- Never auto-activate capabilities.
- Never enable email module permanently.
- Never modify risk-tier definitions.
- Never bypass approval tokens.
- Never access parent filesystem outside workspace root.

---

## 7. Daily Discipline

Before proposing any structural change:

- Verify worktree clean.
- Verify tests green.
- Verify no runtime path tracked.
- Follow docs/ops/daily_operator_checklist.v0.1.md.

---

## 8. Explicit Objective

Goal:

Strengthen workspace as a first-class governed execution domain inside AI-OS.

Outcome:

- Clear separation between canonical system and agent runtime.
- Deterministic agent inbox/outbox model.
- No drift.
- No uncontrolled state mutation.

Deliverable:

- Branch: feature/agent-io-foundation-v0.1
- Tests passing
- DRAFT PR opened
- HALT





# AI-OS Codex Mental Model

## Scope
This file stores my working model for operating, maintaining, and extending AI-OS in this repository.

## What AI-OS Is (Operationally)
- AI-OS is a governed autonomy runtime, not a generic agent app.
- The hard boundary is governance + deterministic execution, not feature velocity.
- Git is treated as system memory; policy and audit artifacts are first-class runtime outputs.

## Runtime Topology (Current)
- Operator entrypoint: `scripts/aiosctl` -> `supervisor.cli`.
- Main control modules:
  - `supervisor/cli.py`: command surface for autonomy, scheduler, capabilities, budgets.
  - `supervisor/supervisor.py`: governance loop and PR gate orchestration.
  - `supervisor/pr_gate/*`: policy load, Gitea fetch, PR evaluation, status publish, artifacts.
  - `supervisor/scheduler/*`: deterministic due-job computation and state progression.
  - `supervisor/capabilities/guard.py`: capability ledger and deny-list enforcement.
  - `supervisor/budgets/store.py` (+ `supervisor/budgets/__init__.py`): deterministic UTC budget windows.
  - `executor/dispatch.py` + `executor/secure_execution_layer/*`: permit-validated execution and audit chain.
  - `orchestrator/git.py`: governed commit mutation boundary + repo/Gitea issue wiring.
  - `autonomy_orchestrator/night_mode.py` and `supervisor/night_executor.py`: night autonomy flow.
- Event/dispatch substrate:
  - `kernel/events.py`, `kernel/dispatch.py`, `kernel/plugins/*`.

## Governance Model (Code Reality)
- Policy source: `governance/policy/pr-governance.v0.2.yaml`.
- PR gate checks include:
  - base branch, head branch regex, feature->develop rule
  - issue reference and PR template completeness
  - lock requirements/exclusivity on high-risk paths
  - required CI checks and supervisor status
  - self-approval and distinct reviewer constraints
  - human approval constraints (especially `main`)
  - system-evolution escalation
  - commit signing required (`gpg`/`ssh`)
- Fail-closed behavior is implemented in multiple layers:
  - policy hash lockdown logic
  - API response validation
  - scheduler/capability/budget deny codes
  - secure execution permit validation + replay checks.

## Determinism and Audit Invariants
- Deterministic ordering and UTC-only time handling are deliberate in scheduler/budgets.
- Budget and state writes favor stable JSON representation.
- Secure execution layer validates event chain semantics and fingerprints.
- Mutation boundary in `create_governed_commit` only commits allowed file set and enforces budget consumption.

## Current Repository State Notes
- Repo has substantial in-flight/dirty work and many untracked files.
- There are overlapping subsystems (legacy + newer):
  - `supervisor/autonomy_budget.py`, `supervisor/autonomy_budget_gate.py`
  - `autonomy_budget/engine.py` (Phase K direction)
- This implies migration/ownership boundaries are not fully consolidated yet.

## My Operating Rules For This Codebase
- Never weaken fail-closed behavior to "best effort."
- Treat governance policy + lock rules + status publishing as kernel-space.
- Prefer explicit deny reason codes over generic exceptions.
- Preserve deterministic outputs and sorted/canonical serialization paths.
- Keep mutation boundaries narrow:
  - stage only allowed files
  - avoid broad `git add .` patterns in governed flows.
- Add tests with every behavior change in gate logic, scheduler, budget, or secure execution.
- Update progress in roadmap.md

## Practical Run/Test Commands
- CLI surface:
  - `./scripts/aiosctl ...`
  - interactive console when no args: `./scripts/aiosctl`
- Quick orchestrator smoke:
  - `python3 -m orchestrator.main_loop`
- Tests:
  - preferred via env with deps installed: `.venv/bin/pytest -q`
  - or `python -m pip install -r requirements.txt -r requirements-dev.txt` then `pytest -q`.

## Immediate Risks To Watch
- Remote URL/API derivation inconsistency across modules (`origin` assumptions still exist in some paths).
- Divergence between architecture docs and active runtime modules.
- Partial rollout risk between budget systems (Phase J/legacy/Phase K).
- CI/workflow split across `.gitea/workflows` and `.github/workflows` may drift.

## Canonical Runtime & Governance Decisions
1. Production control path:
   - `scripts/aiosctl` -> `supervisor/cli.py` is the canonical operator control surface.
   - `supervisor/supervisor.py` is the governance kernel loop and mutation authority.
   - `night_mode` is an orchestration preset on top of the same kernel, not a separate control plane.
2. Authoritative budget system:
   - `supervisor/budgets/*` is canonical.
   - `autonomy_budget/engine.py` remains Phase K direction until full consolidation.
3. Canonical remote:
   - Gitea is canonical for runtime governance decisions.
   - `origin` (GitHub) is optional mirror only and must not drive runtime assumptions.
4. Canonical branch flow:
   - `feature -> develop -> main`.
   - `develop` is integration; `main` is release-grade with stricter governance.
5. Workflow authority:
   - `.gitea/workflows` is authoritative.
   - `.github/workflows` is optional mirror/parity and non-authoritative.
6. Minimum test gate:
   - Feature branch pushes: targeted governance-critical tests allowed.
   - PR to `develop`: full `pytest`.
   - PR to `main`: full `pytest` + strict governance constraints.
   - Governance-critical module changes always require deterministic tests.
7. Legacy/deprecated direction:
   - `supervisor/autonomy_budget.py` and `supervisor/autonomy_budget_gate.py` are compatibility-era modules and should be marked deprecated.
   - Runtime paths assuming `origin` are legacy and should be removed.

## Ownership Intent
Until instructed otherwise, I will optimize for:
- governed safety and deterministic behavior first,
- then reduction of subsystem duplication,
- then developer ergonomics and delivery speed.

This priority ordering is treated as operationally binding.

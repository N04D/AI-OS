# AI-OS Codex Autonomy Roadmap

Status: Phase 1  
Authority: Supervisor (Human)  
Promotion Model: Earned Autonomy  
Fail-Closed: Always

---

## Rules

- Codex may only mark checkboxes.
- Codex may NOT change phase status.
- Promotion requires explicit supervisor approval.
- All changes must preserve deterministic behavior.
- Governance may never be weakened.

---

# Phase 1 — Runtime Consolidation

## Objective
Unify and stabilize the runtime control plane.

## Tasks

- [ ] Remove legacy budget overlap (supervisor/autonomy_budget.py)
- [x] Verified unused
- [x] Eliminate implicit `origin` remote assumptions
- [x] Confirm Gitea is canonical runtime remote
- [x] Ensure night_mode flows through supervisor kernel
- [x] Verify mutation boundary restricts allowed files only
- [x] Confirm deterministic JSON serialization where required
- [x] Confirm UTC-only time handling in scheduler/budgets

## Validation Criteria

- [ ] No duplicate budget logic paths remain
- [x] No implicit remote assumptions
- [x] Night mode executes without manual intervention
- [ ] No fail-open behavior detected
- [x] No broad `git add .` in governed flows

---

# Phase 2 — Deterministic Night Autonomy

## Objective
Night run must be reproducible and stable.

## Tasks

- [ ] Night mode executes full autonomy loop
- [ ] Scheduler deterministic ordering confirmed
- [ ] Budget consumption recorded deterministically
- [ ] Status publication to Gitea verified
- [ ] No non-deterministic timestamps outside controlled areas

## Validation Criteria

- [ ] 3 consecutive successful night runs
- [ ] Identical output for identical state
- [ ] Audit artifacts produced consistently
- [ ] No governance bypass possible

---

# Phase 3 — Governance Hardening

## Objective
Enforce strict policy compliance under stress.

## Tasks

- [ ] Policy hash lockdown verified
- [ ] Required CI checks enforced
- [ ] High-risk path lock enforcement verified
- [ ] Distinct reviewer constraint verified
- [ ] Self-approval rejection confirmed

## Validation Criteria

- [ ] Simulated policy violation fails closed
- [ ] Simulated budget overflow denied
- [ ] Simulated unauthorized mutation blocked
- [ ] Commit signing enforced (gpg or ssh)

---

# Phase 4 — Bounded Self-Improvement

## Objective
Codex may propose internal improvements under governance.

## Tasks

- [ ] Refactor proposals only via governed PR
- [ ] Tests added when governance logic changes
- [ ] No mutation outside allowed boundary
- [ ] Budget consumption accounted for improvements

## Validation Criteria

- [ ] PR gate applied correctly
- [ ] No weakening of governance
- [ ] Deterministic output preserved
- [ ] Supervisor approval granted

---

# Promotion Log

## Phase 1 → Phase 2
Approved by: ____________________  
Date: ____________________  

## Phase 2 → Phase 3
Approved by: ____________________  
Date: ____________________  

## Phase 3 → Phase 4
Approved by: ____________________  
Date: ____________________  

---

End of Roadmap.

# Kernel Control Model v1.0 (ACCIH)

Status: CANONICAL  
Scope: Governs all intake and night-run execution paths  
Applies to: Supervisor, Orchestrator, State, Audit layers  

---

## Overview

AI-OS operates as a governed intake kernel using the ACCIH model:

**A → C → C → I → H**

Acquire → Control → Commit → Integrity → Halt

This model ensures that all actions pass through deterministic intake, explicit governance, atomic execution, integrity verification, and disciplined termination.

---

## 1. Acquire (Intake Layer)

Purpose: Deterministically collect and normalize input.

Sources:
- Local issues (`state/issues/open`)
- Remote Git issues (read-only)

Rules:
- Remote input is data-only (never authority).
- Normalize to canonical schema (`id`, `title`, `body`, `risk_tier`, `source`).
- Strip non-deterministic metadata.
- Sort deterministically:
  - Risk tier (LOW → MED → HIGH)
  - Issue number ascending
  - Source ID as tie-breaker
- Persist normalized set.
- Record intake hash artifact.

Output:
Deterministic issue queue.

---

## 2. Replay Guard (Pre-Control Gate)

Purpose: Prevent duplicate execution.

Rules:
- Maintain `remote_issue_execution_ledger`.
- If issue ID already executed → deny with `DENY_ALREADY_EXECUTED`.
- Write replay-deny audit artifact.
- No side effects on replay.

Output:
Replay-safe queue.

---

## 3. Control (Governance Gates)

Purpose: Enforce policy before execution.

Gates:
- Risk-tier detection (pure function of normalized body)
- Capability registry check
- Approval token check (HIGH only)
- Budget check
- Schema validation

Properties:
- Fail-closed on any violation.
- No implicit downgrade.
- No automatic capability enable.
- No remote override possible.

Output:
ALLOW or DENY (with deterministic reason code).

---

## 4. Commit (Governed Execution)

Purpose: Execute approved work atomically.

Rules:
- Materialize task via governed flow.
- No direct shell or uncontrolled mutation.
- Update:
  - Budget ledger
  - Replay ledger
  - State artifacts
- Write:
  - Execution audit
  - Determinism evidence
  - Capability requests (if applicable)

Output:
Committed state change or deterministic deny artifact.

---

## 5. Integrity (Verification Layer)

Purpose: Ensure consistency and determinism.

Checks:
- State integrity hash verification.
- Determinism evidence validation.
- Phase acceptance verification (if applicable).
- Queue re-check after each execution.

Properties:
- No silent corruption.
- No hidden drift.
- Byte-identical artifacts for identical epoch + state.

---

## 6. Halt Discipline

Purpose: Enforce controlled termination.

Triggers:
- Queue empty
- Budget exhausted
- Governance deny
- Interrupt flag
- Replay-only queue

Actions:
- Persist summary JSON.
- Record halt state.
- Write final audit artifact.
- Return explicit status (`ok`, `stopped`, `halted`).

No background continuation.
No silent loops.

---

## Architectural Separation (Swimlane Summary)

Supervisor:
- Defines policy.
- Makes gate decisions.
- Verifies integrity.
- Enforces halt.

Orchestrator:
- Drives intake and execution loop.
- Applies deterministic ordering.
- Executes only when allowed.

State Store:
- Holds issues, capabilities, budget, replay ledger.
- Persists summary and halt state.

Audit/Logs:
- Records intake hash.
- Records deny artifacts.
- Records execution results.
- Records determinism evidence.

---

## Kernel Guarantees

1. Remote input cannot grant authority.
2. No execution without passing all governance gates.
3. No duplicate execution (replay protected).
4. Deterministic artifacts for identical state + epoch.
5. Budget cannot be bypassed.
6. HIGH-risk changes require explicit approval token.
7. System halts deterministically.

---

## Invariant

Intake → Policy Gates → Atomic Execution → Proof → Halt.

No bypass path exists.

---

Kernel Control Model v1.0  
ACCIH Enforcement Active

# Supervisor Governance Enforcement Spec v0.1

## Purpose

This document defines the mandatory enforcement behavior the
Supervisor must apply to ensure all execution complies with
Governance Contract v0.1.

The Supervisor acts as the **runtime guardian of governance**.
No task execution may proceed without explicit, verifiable
compliance with the Governance Contract.

## Enforcement Principles

1.  **Pre-computation Validation:** Before initiating any
    computation (e.g., dispatching to a BUILDER agent), the
    Supervisor MUST validate that the proposed action,
    its context, and its intended outcome adhere to
    Governance Contract v0.1.

2.  **Immutability of Governance:** The Governance Contract
    v0.1, once loaded, MUST be treated as an immutable
    constitutional document. Any attempt by a task or
    sub-agent to alter the Governance Contract without
    explicit, authorized amendment procedures MUST be
    rejected and flagged as a critical governance violation.

3.  **Atomic Compliance Checks:** All governance checks
    MUST be atomic and performed before any irreversible
    actions are taken (e.g., committing code, modifying
    critical system state).

4.  **Logging and Reporting:** Any detected governance
    violation MUST be immediately logged, and a critical
    alert MUST be issued. The Supervisor MUST refuse to
    proceed with the non-compliant task.

5.  **Delegation of Authority:** The Supervisor maintains
    ultimate authority over governance enforcement. While
    sub-agents (like the BUILDER) may perform pre-checks,
    the final determination of compliance rests with the
    Supervisor.

## Enforcement Mechanisms (Conceptual)

-   **Context Loading:** The Supervisor MUST load
    `docs/governance.md` and `agents/state/environment.json`
    at startup to establish its constitutional and environmental
    context.

-   **Instruction Validation:** When generating or receiving
    instructions for BUILDER agents, the Supervisor MUST
    validate these instructions against:
    -   **Role Separation:** Ensure the instructions do not
        violate the defined roles (e.g., PLANNER not
        generating production code).
    -   **Allowed Actions:** Verify instructions only
        contain permitted actions (e.g., no uncontrolled
        architectural changes).
    -   **Deterministic Behavior:** Confirm instructions
        lead to predictable, testable outcomes.

-   **Commit Policy Enforcement:** The Supervisor MUST
    review proposed commits (e.g., from a BUILDER agent)
    before they are finalized, ensuring:
    -   **Affected Files:** Only files explicitly allowed by
        the task are modified.
    -   **Commit Message Format:** Adherence to defined
        commit message conventions.
    -   **Content Compliance:** No introduction of forbidden
        patterns or violation of core principles.

-   **Resource Access Control:** (Future) The Supervisor
    will mediate access to critical system resources,
    ensuring agents only interact with allowed components.

## Compliance Reporting

The Supervisor MUST include a section in its reports
confirming its adherence to the Governance Contract,
including any detected violations or enforcement actions taken.

## Future Revisions

This specification may be revised to include more granular
enforcement rules, integration with security policies,
and advanced anomaly detection mechanisms. All revisions
MUST follow the amendment procedures outlined in
Governance Contract v0.1.

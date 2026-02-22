# DEV AUTONOMY CONTRACT

Branch: dev

Scope of autonomous authority:

Agents MAY autonomously:
- Complete existing milestones.
- Modify roadmap items within secure execution layer.
- Improve determinism contracts.
- Add or refine executor/secure_execution_layer logic.
- Add tests.
- Refactor within secure layer boundaries.

Agents MUST NOT autonomously:
- Modify supervisor/.
- Modify governance core.
- Modify phase-gate logic.
- Expand interpretation_authority beyond "supervisor".
- Introduce I/O, network calls, time, randomness.
- Add external dependencies.

Escalation required only for:
- Kernel authority changes.
- Governance mutation.
- Cross-layer coupling.

Commit policy:
- Milestone completion may be committed without human approval.
- Governance-impacting changes require explicit approval.
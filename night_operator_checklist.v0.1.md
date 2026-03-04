NIGHTLY SELF-IMPROVEMENT CYCLE (AI-OS)

Goal: Produce at most ONE draft PR that advances the roadmap without weakening governance.

Inputs:

- docs/roadmap/codex_autonomy_roadmap.md (focus on open items)
- docs/core_manifest.md (ACCIH invariants)
- docs/specs/self_improvement_risk_tiers.v0.1.md
- docs/specs/self_improvement_proposal.v0.1.md
- docs/specs/determinism_evidence.schema.v0.1.json

Rules:

- Work only in your workspace repo.
- Create a branch from main/dev (follow repo policy).
- Choose ONE risk tier (LOW/MED/HIGH).
- Add/update tests. Full suite must pass.
- Open a DRAFT PR and HALT.

Nightly Execution Contract:

- The autonomous work cycle runs at night (cron-driven) in deterministic mode.
- At end of the nightly run, the agent writes a concise build report artifact.
- The report is queued for morning delivery at 09:30 local operator time.
- Sending at 09:30 does not require the agent to be active at that time.
- The send worker only dispatches pre-generated queued reports.
- If queue state is invalid, fail closed (no silent send).

Morning Report Minimum Content:

- Date/epoch
- What was built (PR title/number, commits, files touched)
- Why it was built (roadmap item + issue reference)
- Verification summary (tests, pass/fail, deterministic evidence when required)
- Next planned action or explicit HALT reason

Why this should be added:

- It improves operator visibility without increasing night-time control overhead.
- It preserves deterministic autonomy: generation and dispatch are separated.
- It reduces missed progress by creating a fixed daily review ritual.
- It keeps governance auditable with a stable, timestamped report path.

Vision alignment:

- Fits the AI-OS principle of structured autonomy: autonomous execution, governed communication.
- Supports fail-closed operation: no report send on invalid queue/state.
- Strengthens human-agent collaboration: operator gets clear morning situational awareness.
- Reinforces constitutional boundaries: report is informational, not authority escalation.

Deliverable:

- PR link
- Risk tier
- Test summary
- Evidence references (if MED/HIGH)
- Morning report queue record for 09:30 dispatch
- HALT

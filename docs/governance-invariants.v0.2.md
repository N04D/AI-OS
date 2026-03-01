# Governance Invariants v0.2

- Baseline commit SHA: `9ff122487c6203e44092702e4ed672f50b98d2e9`
- Exact pytest summary: `335 passed, 2 warnings in 5.18s`
- Included autonomy phases: A, B, C, D, E, F, G, H

Scheduler invariants:
- Target architecture: Model C (scheduler as skill under capability-control)
- Shipping default: `event_only`
- `guarded_skill` requires capability: `scheduler_guarded_skill_run`
- Scheduler never bypasses mutation boundary guard / secure layer / PR gate

Capability invariants:
- Explicit request artifacts + approval markers are required for grants
- TTL supported (`expires_at = null` is permanent; enforcement is read-time)
- Revoke supported, with optional emergency deny-list

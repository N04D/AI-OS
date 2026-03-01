# 01 Governance Model

## Purpose
Define governance controls currently enforced in code for capabilities, revocations, scheduler operation, and autonomy budgets.

## Current Behavior

### Capability grant/revoke model
- Capability ledger source: `state/supervisor_capabilities.json`.
- Backward compatibility: boolean entries are normalized into structured entries.
- Revocation request artifact schema: `governance/schema/supervisor/capability-revoke.v0.1.json`.
- Request path pattern: `requests/capabilities/revoke/<timestamp>__<capability>__<reason>.json`.
- Approval marker path: `approvals/capabilities/revoke/<revoke_id>.approved`.
- `aiosctl autonomy request-revoke` writes request + local commit.
- `aiosctl autonomy apply-revoke` validates request+approval+baseline and mutates ledger deterministically.

### Emergency deny-list
- Optional deny-list file: `state/supervisor_capability_denies.json`.
- If capability is listed under `deny`, access is denied at read-time with `DENY_CAPABILITY_EMERGENCY`.
- Deny-list does not mutate capability grants.

### Scheduler governance scope
- Scheduler job schema: `governance/schema/scheduler/job.v0.1.json`.
- Only `interval_minutes` schedules are allowed.
- Modes: `event_only` and `guarded_skill`.
- `guarded_skill` requires `payload.task` and capability guard in runtime path.

### Budget governance
- Phase J enforced budgets: `state/budgets.json` (`v0.1`, UTC, daily windows).
- Enforced keys: `scheduler_guarded_skill_run`, `low_risk_pr_merge`.
- Mutation boundary and guarded skill execution both consume budget and deny on overrun.

### Phase K policy-driven governance (standalone engine)
- Policy file: `governance_policy.yaml`.
- Strict schema keyset is required (`require_all_keys=true`, `forbid_unknown_keys=true`).
- Defines trust levels, risk profiles, per-skill quotas, trust evolution, cross-agent risk propagation, and ledger rules.

## Fail-Closed Rules
- Missing/invalid revoke request, approval, baseline, or schema fields deny revoke application.
- Unknown/missing capabilities deny guarded skill execution.
- Expired grants deny execution.
- Missing/invalid budget state denies budgeted authority points.
- Missing/invalid Phase K policy or state denies Phase K operations.

## Security Boundaries
- Governance mutation via revoke is commit-mediated and requires explicit approval artifact.
- Scheduler cannot self-grant capabilities.
- Emergency deny-list can immediately block capability execution without rewriting grants.
- PR-gate and policy semantics are unchanged by the current autonomy extensions.

## Determinism Guarantees
- Revoke and state writes are sorted JSON with stable field serialization.
- Scheduler config and state validators require exact key sets and UTC timestamps.
- Phase K policy validation requires exact top-level key set and exact canonical JSON spec string.

## Known Limitations / TODOs
- No automated governance reconciler; operator actions are explicit CLI-driven.
- Phase K governance checks are available in `autonomy_budget.engine` but not yet integrated into existing supervisor CLI entrypoints.

## Cross-links
- [04 Dispatch and Capability Gate](./04-Dispatch-and-Capability-Gate.md)
- [06 Operator Config and Audit](./06-Operator-Config-and-Audit.md)
- [07 Error Code Registry](./07-Error-Code-Registry.md)

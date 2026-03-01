# Supervisor Autonomy v0.2

## Phase F: Governed Capability Revocation

Phase F adds governed revocation for supervisor capabilities and preserves deterministic enforcement.

- `aiosctl autonomy request-revoke --cap <capability> --why "<justification>"`
  - Writes revoke request artifact at `requests/capabilities/revoke/<timestamp>__<capability>__<reason_slug>.json`.
  - Creates a local commit: `chore(capabilities): request revoke <capability>`.
  - Does not mutate `state/supervisor_capabilities.json`.

- `aiosctl autonomy apply-revoke --request <request_path> --approval <approval_path>`
  - Requires approval marker at `approvals/capabilities/revoke/<revoke_id>.approved`.
  - Validates revoke schema fields, approval linkage, and `baseline_commit == HEAD`.
  - Mutates `state/supervisor_capabilities.json` deterministically by setting:
    - `granted=false`
    - `revoked_at`
    - `revoked_by`
    - `source_revoke_id`
  - Preserves historical grant fields such as `earned_at` and `granted_at`.
  - Creates a local commit: `chore(capabilities): revoke <capability> via <revoke_id>`.

Deterministic deny reason codes for revoke workflow:

- `DENY_CAPABILITY_REVOKE_INVALID`
- `DENY_CAPABILITY_REVOKE_MISMATCH`
- `DENY_CAPABILITY_REVOKE_BASELINE_MISMATCH`

## Optional Emergency Deny-List (Read-Time Kill-Switch)

Phase F optionally supports `state/supervisor_capability_denies.json`:

```json
{
  "deny": ["high_risk_pr_merge"],
  "updated_at": "2026-02-25T00:00:00Z"
}
```

Behavior:

- If a capability appears in `deny`, capability checks return `DENY_CAPABILITY_EMERGENCY`.
- This path is read-time only and does not mutate capability grants.

## Explicit Non-Changes

- No auto-merge behavior is introduced.
- Approval marker is mandatory for apply-revoke.
- No self-grant behavior is introduced.
- No PR-gate semantics changes.
- No governance policy changes.

## Phase G: Scheduler-as-Skill (Event-Only Default)

Phase G introduces a minimal deterministic scheduler layer under autonomy controls.

- `aiosctl autonomy scheduler tick [--now "<UTC ISO8601>"] [--dry-run]`
  - Loads and validates `state/scheduler_jobs.json`.
  - Computes due jobs deterministically in UTC only.
  - Emits `scheduler.job_due` events in lexical `job_id` order.
  - In non-dry-run mode writes deterministic runtime state to `state/scheduler_state.json`.

Event envelope:

```json
{
  "type": "scheduler.job_due",
  "job_id": "nightly_audit",
  "payload": {"task": "nightly_audit"},
  "fired_at": "2026-02-25T12:00:00Z"
}
```

Capability boundary for Model C foundation:

- Jobs support `mode`: `event_only` or `guarded_skill`.
- Default remains `event_only`.
- `guarded_skill` requires explicit capability grant: `scheduler_guarded_skill_run`.
- Without that capability, scheduler run output records deterministic deny (`DENY_CAPABILITY_MISSING` or `DENY_CAPABILITY_EXPIRED`).
- Guarded execution uses a whitelisted internal handler registry only (no arbitrary command execution).

Deterministic deny reason codes for scheduler flow:

- `DENY_SCHEDULER_CONFIG_INVALID`
- `DENY_SCHEDULER_STATE_INVALID`
- `DENY_SCHEDULER_TIME_INVALID`
- `DENY_SCHEDULER_MODE_UNSUPPORTED_V0`

Phase G non-goals remain explicit:

- Scheduler does not get mutation authority by itself.
- Scheduler does not bypass guard/secure-layer/PR-gate boundaries.
- No governance policy enforcement changes.
- No auto-merge, auto-grant, or auto-renew.

# 07 Error Code Registry

## Purpose
Provide a current registry of operational deny/error codes emitted by autonomy, scheduler, capability, budget, event bus, dispatch, and plugin subsystems.

## Current Behavior
Codes below are grouped by subsystem and reflect currently present constants and return surfaces in code.

### Budget / quota / trust
- `DENY_BUDGET_EXCEEDED`
- `DENY_BUDGET_STATE_INVALID`
- `DENY_LEDGER_APPEND_FAILED`
- `DENY_LEDGER_CHAIN_INVALID`
- `DENY_SKILL_QUOTA_EXCEEDED`
- `DENY_ESCALATION_REQUIRED`
- `DENY_STATE_INVALID`
- `DENY_POLICY_MISSING`
- `DENY_POLICY_INVALID`

### Capability governance and guard
- `DENY_CAPABILITY_MISSING`
- `DENY_CAPABILITY_EXPIRED`
- `DENY_CAPABILITY_EMERGENCY`
- `DENY_CAPABILITY_NOT_GRANTED`
- `DENY_CAPABILITY_NOT_ALLOWED`
- `DENY_CAPABILITY_NOT_DECLARED`
- `DENY_CAPABILITY_REVOKE_INVALID`
- `DENY_CAPABILITY_REVOKE_MISMATCH`
- `DENY_CAPABILITY_REVOKE_BASELINE_MISMATCH`

### Scheduler
- `DENY_SCHEDULER_CONFIG_INVALID`
- `DENY_SCHEDULER_STATE_INVALID`
- `DENY_SCHEDULER_TIME_INVALID`
- `DENY_SCHEDULER_MODE_UNSUPPORTED_V0`
- `DENY_SCHEDULER_TASK_UNKNOWN`
- `DENY_SCHEDULER_TASK_FAILED`

### Plugin loader / runtime
- `DENY_SCHEMA_MISSING`
- `DENY_SCHEMA_INVALID`
- `DENY_SCHEMA_VALIDATION`
- `DENY_POLICY_PARSE_ERROR`
- `DENY_MANIFEST_NOT_MAPPING`
- `DENY_PLUGIN_COMMAND_MISSING`
- `DENY_PLUGIN_COMMAND_INVALID`
- `DENY_PLUGIN_NOT_FOUND`
- `DENY_PLUGIN_DISABLED`
- `DENY_PLUGIN_TIMEOUT`
- `DENY_PLUGIN_REPEATED_FAILURE`
- `DENY_PLUGIN_PROTOCOL`
- `DENY_ARTIFACT_PATH_ESCAPE`
- `DENY_UNKNOWN`

### PR gate / governance checks
- `DENY_BASE_BRANCH_NOT_ALLOWED`
- `DENY_REQUIRED_STATUS_CHECKS`
- `DENY_SUPERVISOR_STATUS_REQUIRED`
- `DENY_COMMIT_UNSIGNED`
- `DENY_COMMIT_UNVERIFIABLE`
- `DENY_COMMIT_SIGNING_MODE_INVALID`
- `DENY_COMMIT_SIGNING_TYPE_UNKNOWN`
- `DENY_COMMIT_SIGNING_TYPE_UNACCEPTED`

### Communication / policy envelope
- `DENY_CHAT_NOT_ALLOWED`
- `DENY_NO_MESSAGE`
- `DENY_PATH_VIOLATION`
- `DENY_FORBIDDEN_FILESYSTEM_PATH`
- `DENY_FORBIDDEN_CAPABILITY`
- `DENY_NETWORK_ALLOWLIST_REQUIRED`
- `DENY_SECRET_MISSING`
- `DENY_SECRET_INVALID`
- `DENY_BAD_JSON`
- `DENY_AUDIT_WRITE_FAILED`
- `DENY_WORKFLOW_MISSING_TOKEN`
- `DENY_WORKFLOW_MISSING_API_BASE`

### Email gateway
- `DENY_AGENT_NOT_REGISTERED`
- `DENY_AGENT_CHANNEL_DISABLED`
- `DENY_CAPABILITY_MISSING`
- `DENY_ADDRESS_NOT_ALLOWED`
- `DENY_DOMAIN_NOT_ALLOWED`
- `DENY_BODY_TOO_LARGE`
- `DENY_REPLY_NOT_ALLOWED`
- `DENY_REPLY_RATE_LIMITED`

### Kernel dispatch/event bus (non-DENY families)
- Dispatch: `DISPATCH_INVALID_ARGS`, `DISPATCH_RUNNER_REFUSED`, `DISPATCH_RUNNER_ERROR`, `DISPATCH_INTERNAL_ERROR`
- Event bus: `EVENT_BUS_INVALID_ARGS`, `EVENT_BUS_REGISTRY_UNREADABLE`, `EVENT_BUS_CONFIG_UNREADABLE`, `EVENT_BUS_STATE_INVALID`, `EVENT_BUS_AUDIT_LOG_WRITE_FAILED`, `EVENT_BUS_MANIFEST_UNREADABLE`, `EVENT_BUS_EXTERNAL_NOT_ALLOWED`, `EVENT_BUS_DISPATCH_FAILED`

## Fail-Closed Rules
- All unknown/invalid policy, state, schema, capability, or ledger conditions must return explicit failure codes.
- Write failures in audit/ledger paths fail operation rather than degrade silently.

## Security Boundaries
- Error codes are part of machine contract for gating decisions.
- Deny codes must not be remapped silently by operator tooling.

## Determinism Guarantees
- Error selection in deterministic subsystems is stable for identical inputs.
- PR gate primary failure uses explicit severity ordering.

## Known Limitations / TODOs
- Some legacy modules return exception text codes outside standardized `DENY_*` namespace.
- Code registry is currently maintained manually; automated extraction could reduce drift.

## Cross-links
- [01 Governance Model](./01-Governance-Model.md)
- [04 Dispatch and Capability Gate](./04-Dispatch-and-Capability-Gate.md)
- [09 Testing and Verification](./09-Testing-and-Verification.md)

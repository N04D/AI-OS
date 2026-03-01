# 04 Dispatch and Capability Gate

## Purpose
Define capability checks, dispatch gates, and authority points where autonomous actions are allowed or denied.

## Current Behavior

### Capability gate paths
- `supervisor.capabilities.guard.check_capability()` validates:
  - emergency deny-list (`DENY_CAPABILITY_EMERGENCY`)
  - grant presence (`DENY_CAPABILITY_MISSING`)
  - expiry (`DENY_CAPABILITY_EXPIRED`)
- Required scheduler capability constant: `scheduler_guarded_skill_run`.

### Scheduler guarded_skill gate
1. Due event emitted first (`scheduler.job_due`).
2. Capability gate evaluated.
3. Budget key `scheduler_guarded_skill_run` consumed.
4. Whitelisted handler executed (`supervisor.scheduler.handlers`).
5. Result artifact written under `logs/control/scheduler_runs/...`.

### Kernel dispatch gate
- `kernel.dispatch` validates plugin/method/payload args.
- Allowed methods loaded from plugin manifest `methods`; default is `on_event`.
- Runner failures mapped into dispatch error classes.

### PR gate relation
- PR gate evaluator (`supervisor/pr_gate/evaluator.py`) remains separate and unchanged in semantics.
- Autonomy budget/capability checks do not bypass PR gate requirements.

## Fail-Closed Rules
- Unknown capability or emergency deny-list membership blocks execution.
- Unknown scheduler task produces `DENY_SCHEDULER_TASK_UNKNOWN`.
- Method not listed in plugin manifest returns method refusal.
- Invalid dispatch args return `DISPATCH_INVALID_ARGS`.

## Security Boundaries
- Guarded skill path has no self-grant path.
- Dispatch is bounded by manifest-declared methods and runner policy.
- Mutation still requires orchestrator boundary checks even after scheduler allow.

## Determinism Guarantees
- Scheduler due computation and ordering are deterministic.
- Capability checks use explicit UTC comparisons.
- Dispatch request ID deterministic fallback uses hash over request tuple.

## Known Limitations / TODOs
- Scheduler task registry currently includes only `nightly_audit`.
- Capability enforcement for non-scheduler operations is subsystem-specific, not globally centralized in one gate function.

## Cross-links
- [01 Governance Model](./01-Governance-Model.md)
- [03 Execution Boundary](./03-Execution-Boundary.md)
- [05 Event Bus](./05-Event-Bus.md)

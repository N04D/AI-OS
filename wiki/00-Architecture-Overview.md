# 00 Architecture Overview

## Purpose
This page defines the current AI-OS runtime architecture, focusing on deterministic autonomy controls, execution boundaries, and auditability.

## Current Behavior

### High-level topology

```text
operator -> scripts/aiosctl -> supervisor.cli
                         |-> autonomy gates (promote/intake/materialize/dryrun)
                         |-> capability revoke workflow
                         |-> scheduler tick (event_only + guarded_skill)

supervisor.cli -> supervisor.scheduler.* -> kernel.events.emit -> kernel.dispatch -> plugin runner
             \-> supervisor.capabilities.guard (ledger + emergency deny-list)
             \-> supervisor.budgets.store (daily UTC budget enforcement)
             \-> orchestrator.git.create_governed_commit (mutation boundary + budget)
             \-> supervisor.channels.email_gateway (governed send/poll)

Phase K module (new, standalone):
  autonomy_budget.engine.BudgetEngine
  - policy-driven trust/risk/quota math
  - hash-chained epoch ledger
  - read-only inspection CLI entrypoint
```

### Core runtime components
- `supervisor/cli.py`: primary operator/autonomy command surface.
- `supervisor/scheduler/config.py`, `engine.py`, `state.py`, `handlers.py`: deterministic scheduler.
- `supervisor/capabilities/guard.py` + `supervisor/autonomy_capabilities.py`: capability allow/deny and governed revocation.
- `supervisor/budgets/store.py`: Phase J budget store and deterministic daily rollover.
- `orchestrator/git.py`: governed commit path and mutation boundary budget check.
- `kernel/events.py` and `kernel/dispatch.py`: event fan-out and plugin method dispatch.
- `autonomy_budget/engine.py`: Phase K policy-driven trust/risk/skill-quota + ledger subsystem.
- `supervisor/channels/email_gateway.py` + `tools/mail_worker.py`: governed email send/poll + queued SMTP worker.

### Canonical state and artifacts
- Scheduler config: `state/scheduler_jobs.json`
- Scheduler runtime state: `state/scheduler_state.json`
- Capability ledger: `state/supervisor_capabilities.json`
- Emergency capability deny-list (optional): `state/supervisor_capability_denies.json`
- Phase J budget state: `state/budgets.json`
- Scheduler events fallback artifacts: `logs/control/events/<date>/scheduler.job_due__<job_id>__<ts>.json`
- Scheduler guarded_skill run artifacts: `logs/control/scheduler_runs/<date>/<job_id>__<ts>.json`
- Phase K policy file: `governance_policy.yaml`
- Phase K epoch ledger: `audit/budget_ledger/<YYYY-MM-DD>.jsonl`

## Fail-Closed Rules
- Missing/invalid scheduler config or state denies tick with stable scheduler deny codes.
- Missing capability grant, expired capability, or emergency deny-list entry denies guarded skill.
- Invalid/missing budget state denies guarded skill and commit boundary paths.
- Phase K budget engine denies on missing policy, invalid policy, invalid state, ledger append failure, or chain verification failure.
- Plugin/event dispatch returns explicit failure surfaces when registry/config/manifest/dispatch steps fail.

## Security Boundaries
- Mutation boundary: `orchestrator/git.py:create_governed_commit` checks changed files against allowed set and budget before commit.
- Guarded scheduler execution requires capability `scheduler_guarded_skill_run`; unknown tasks are denied.
- Plugin boundary is out-of-process with manifest+policy validation and capability/method restrictions.
- Secure execution layer provides permit validation and replay checks for executor dispatch path.

## Determinism Guarantees
- Scheduler uses UTC timestamps and lexical job ordering.
- Budget store rolls windows by UTC day only and writes sorted deterministic JSON.
- Event fallback artifacts are stable JSON records with sorted keys.
- Phase K ledger hashing uses canonical JSON (`sort_keys=True`, `separators=(',',':')`, `ensure_ascii=True`).

## Known Limitations / TODOs
- Phase K engine is implemented and tested but not yet wired into `supervisor.cli` command tree.
- Some legacy autonomy budget modules (`supervisor/autonomy_budget.py`, `supervisor/autonomy_budget_gate.py`) coexist with Phase J/Phase K paths.
- Scheduler runtime still depends on explicit operator `tick`; optional user-level systemd daemon exists for email auto loop.

## Cross-links
- [01 Governance Model](./01-Governance-Model.md)
- [03 Execution Boundary](./03-Execution-Boundary.md)
- [04 Dispatch and Capability Gate](./04-Dispatch-and-Capability-Gate.md)
- [05 Event Bus](./05-Event-Bus.md)
- [06 Operator Config and Audit](./06-Operator-Config-and-Audit.md)

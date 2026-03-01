# 09 Testing and Verification

## Purpose
Document current verification status, subsystem test coverage, and deterministic replay checks.

## Current Behavior

### Latest suite status
- Full repository run:
  - `351 passed, 2 warnings in 5.48s`
- Warnings observed are pytest cache permission warnings, not functional failures.

### Phase-focused coverage highlights
- Scheduler schema and determinism:
  - `tests/test_scheduler_schema.py`
  - `tests/test_scheduler_engine_determinism.py`
  - `tests/test_aiosctl_scheduler_tick.py`
- Guarded skill and capability enforcement:
  - `tests/test_scheduler_guarded_skill.py`
  - `tests/test_capability_emergency_denylist.py`
- Phase J budgets:
  - `tests/test_budget_store.py`
  - `tests/test_scheduler_budget_enforcement.py`
  - `tests/test_commit_budget_enforcement.py`
  - `tests/test_budgets.py`
  - `tests/test_orchestrator_git_budget.py`
- Phase K policy/trust/risk/quota/ledger:
  - `tests/test_phase_k_budget.py`

### Determinism and replay checks
- Scheduler tests inject fixed `--now` UTC timestamps.
- Budget tests assert deterministic daily rollover and stable deny codes.
- Phase K tests validate:
  - trust upgrade/downgrade transitions
  - risk-adjusted budget/quota behavior
  - hash-chain tamper detection
  - replay output determinism across repeated runs
  - fail-closed on missing policy, invalid state, append failure

## Fail-Closed Rules
- Tests intentionally assert explicit rejection codes for invalid config/state/capability/budget conditions.
- Ledger tampering must produce chain verification failure.

## Security Boundaries
- Test suite validates enforcement points only at intended authority boundaries:
  - scheduler guarded_skill
  - governed commit path
- No tests indicate bypass of PR-gate/governance semantics.

## Determinism Guarantees
- Test inputs use fixed UTC timestamps and controlled fixtures.
- Canonical serialization and sorted outputs are validated in multiple paths.

## Known Limitations / TODOs
- Phase K currently validated via module-level tests; integration tests with `supervisor.cli` are pending because runtime wiring is not complete.
- Broader cross-subsystem replay tests (event bus + phase K ledger correlation) are not yet present.

## Cross-links
- [00 Architecture Overview](./00-Architecture-Overview.md)
- [06 Operator Config and Audit](./06-Operator-Config-and-Audit.md)
- [08 Security Invariants](./08-Security-Invariants.md)

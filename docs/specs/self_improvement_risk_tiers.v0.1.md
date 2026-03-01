# Self-Improvement Risk Tiers v0.1

Canonical risk-tier specification for governed self-improvement.

## Tier Definitions

- `LOW`: Docs/tests only, no runtime logic changes.
- `MED`: Refactor preserving behavior (runtime changes allowed with explicit scope).
- `HIGH`: Scheduler, budget, governance, approval tokens, phase acceptance, integrity.

## Enforcement Requirements

- Every self-improvement PR must declare one tier in proposal.
- `HIGH` requires explicit approval token evidence.
- `MED` and `HIGH` require determinism evidence.
- Tier classification and decision must be recorded in audit output.

## Determinism Rule

For `MED` and `HIGH`, proposal must include deterministic evidence references:

- identical-input/identical-output proof
- rerun consistency evidence for runtime changes

## Fail-Closed Conditions

- Missing tier classification -> deny
- `HIGH` without approval token -> deny
- `MED/HIGH` without determinism evidence -> deny

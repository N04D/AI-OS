# Phase Acceptance Rule v0.1 (Canonical)

This is the single canonical rule source for phase completion acceptance.

## Contract

A phase MUST NOT be marked complete unless all checks pass:

1. Full `pytest` run has `failed = 0`.
2. Roadmap update is recorded.
3. Progress update is recorded.
4. HALT state is entered.
5. Any skipped tests are explicitly justified and recorded.

## Deterministic Evidence Schema

Input evidence is a JSON object with exact keys:

- `version` (must be `v0.1`)
- `pytest`:
  - `passed` (int >= 0)
  - `failed` (int >= 0, must be `0`)
  - `skipped` (int >= 0)
  - `skip_justifications` (list of non-empty strings)
- `roadmap_updated` (bool, must be `true`)
- `progress_updated` (bool, must be `true`)
- `halt_entered` (bool, must be `true`)

For deterministic skip handling:

- if `skipped > 0`, then `len(skip_justifications) == skipped`.
- if `skipped == 0`, then `skip_justifications` MAY be empty.

No wall-clock or runtime-now comparisons are allowed for this rule.

## Enforcement

Use:

```bash
aiosctl --json autonomy phase-acceptance verify --evidence-path <path>
```

Fail-closed behavior:

- any schema mismatch -> rejected
- any unmet contract condition -> rejected
- only fully valid evidence -> accepted

## Primary Deny Codes

- `DENY_PHASE_ACCEPTANCE_SCHEMA_INVALID`
- `DENY_PHASE_ACCEPTANCE_PYTEST_FAILED`
- `DENY_PHASE_ACCEPTANCE_ROADMAP_MISSING`
- `DENY_PHASE_ACCEPTANCE_PROGRESS_MISSING`
- `DENY_PHASE_ACCEPTANCE_HALT_MISSING`
- `DENY_PHASE_ACCEPTANCE_SKIP_JUSTIFICATION_MISSING`

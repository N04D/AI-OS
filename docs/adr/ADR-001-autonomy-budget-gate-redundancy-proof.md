# ADR-001: autonomy_budget_gate Redundancy Proof

- Status: Accepted
- Date: 2026-02-27
- Source Proof: `docs/roadmap/autonomy_budget_gate_redundancy_proof.md`

## Context
Legacy compatibility layer `supervisor/autonomy_budget_gate.py` required proof of runtime redundancy before removal.

## Decision
Treat `autonomy_budget_gate` as non-canonical compatibility-only path and remove from runtime dependency graph.

## Evidence
- Dependency scan showed no production imports from runtime paths.
- Runtime budget checks route through canonical budget implementation.
- Compatibility behavior check showed equivalent allow/consume outcomes across tested actions.

## Consequences
- Canonical budget path remains single-source.
- Governance surface reduced.
- Future budget work must target canonical budget module only.

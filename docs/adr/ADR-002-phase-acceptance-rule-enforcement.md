# ADR-002: Permanent Phase Acceptance Rule Enforcement

- Status: Accepted
- Date: 2026-02-27
- Source Proof: `docs/phase-acceptance-rule.v0.1.md`

## Context
Phase closure needed deterministic fail-closed enforcement beyond manual process.

## Decision
Adopt a canonical phase acceptance contract enforced by verification tooling before phase completion can be claimed.

## Evidence
- Canonical rule document defines acceptance contract.
- Automated verifier introduced and tested with positive/negative cases.
- Contract requires green suite, roadmap/progress updates, and HALT evidence.

## Consequences
- Phase completion claims are machine-verifiable.
- Missing governance evidence blocks closure deterministically.

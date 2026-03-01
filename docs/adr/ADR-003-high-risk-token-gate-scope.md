# ADR-003: High-Risk Token Gate Scope in Night Mode

- Status: Accepted
- Date: 2026-02-27
- Source Proof: `docs/roadmap/codex_autonomy_progress.md`

## Context
Night-mode token checks were interpreted as broad execution gates.

## Decision
Restrict approval-token enforcement for capability execution in night mode to HIGH-risk self-improvement tasks only.
LOW/MED self-improvement tasks remain governed by capability + budget + policy checks.

## Evidence
- Runtime gate condition is explicitly HIGH-only.
- No-token LOW/MED run executes eligible task and denies missing capability deterministically.
- Full suite remained green after validation.

## Consequences
- Removes unnecessary token friction for LOW/MED deterministic work.
- Preserves strict gate for HIGH-risk actions.

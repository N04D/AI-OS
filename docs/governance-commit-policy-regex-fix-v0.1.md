# Governance Commit-Policy Regex Fix Spec v0.1

## Purpose

This specification defines a minimal, deterministic fix for the GovernanceEnforcer
commit-policy extractor so that `validate_commit_policy()` is reliable and can be
used as an atomic pre-commit gate.

This spec exists because the current regex used to extract backticked file paths
from instruction text causes a runtime regex compilation error on Python 3.13:

`re.PatternError: bad character range \\-/ at position ...`

This breaks governed execution by preventing commit-policy validation.

## Scope

- Modify ONLY: `supervisor/governance_enforcement.py`
- Do NOT refactor architecture.
- Do NOT change behavior unrelated to allowed-files extraction.
- Do NOT change validation semantics beyond making the regex valid and deterministic.

## Root Cause

The current extractor uses a character class with an invalid range:

`r"`([A-Za-z0-9_.\\-/]+)`"`

Within `[...]`, the hyphen (`-`) defines a range unless placed at the start/end or escaped.
In Python 3.13, the current placement leads to an invalid range and crashes.

## Required Behavior

### Allowed Files Extraction

The extractor MUST:

- Extract only paths wrapped in backticks.
- Allow these characters in extracted paths:
  - letters A–Z, a–z
  - digits 0–9
  - underscore `_`
  - dot `.`
  - forward slash `/`
  - backslash `\`
  - hyphen `-`

### Determinism

- Extraction must be purely functional (no IO).
- Output must be deterministic for identical input.

## Implementation Requirement

Replace the invalid pattern with a valid equivalent that supports the same intended
character set.

Acceptable options:

### Option A (preferred)
Use a safe character class with hyphen at the end:

- Pattern:
  - ``r"`([A-Za-z0-9_.\\/\\-]+)`"``

### Option B
Escape hyphen explicitly:

- Pattern:
  - ``r"`([A-Za-z0-9_.\\/\\-]+)`"``

Both are acceptable if they compile under Python 3.13 and preserve extraction behavior.

## Verification

Before commit, run:

1) `python3 -m py_compile supervisor/governance_enforcement.py`

2) Minimal runtime proof (must not crash):
- Execute a small snippet that calls `_extract_allowed_files()` with an instruction text
  containing:
  - `executor/dispatch.py`
  - `supervisor/supervisor.py`
  - `docs/governance.md`

Expected:
- returns a set containing the same three paths
- no exception

## Commit Rules

- Stage ONLY: `supervisor/governance_enforcement.py`
- Single commit message:
  - `fix(governance): repair allowed-files regex extraction`
- No other file changes.

## Outcome

After this fix, `validate_commit_policy()` must be able to run as an atomic gate,
enabling governed execution cycles where commit policy is verified before any commit.

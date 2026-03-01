# Self-Improvement Proposal v0.1

Status: Draft
Proposal ID: `<self-improvement-YYYYMMDD-###>`
Author: `<name>`
Date (UTC): `<YYYY-MM-DD>`
PR: `<url-or-tbd>`
Label: `self-improvement`

## Problem Statement

Describe the concrete problem being addressed.

## Risk Tier

Choose exactly one:

- [ ] LOW
- [ ] MED
- [ ] HIGH

Justification:

## Affected Components

List all affected modules, paths, and interfaces.

## Allowed Mutation Scope

List exact files/directories intended for mutation.

## Determinism Impact

Describe determinism impact and controls:

- Expected deterministic invariants preserved
- Any potential sources of nondeterminism
- How nondeterminism is prevented

## Test Plan (Mandatory)

Required:

- Targeted tests to add/update
- Full-suite verification command
- Expected outcomes

Command(s):

```bash
pytest -q
```

## Determinism Evidence

Provide evidence artifact references (or plan to produce them):

- `determinism_evidence.json`: `<path-or-tbd>`
- Identical-input/identical-output proof: `<path-or-tbd>`

## Approval Token

Required for HIGH-risk only:

- token reference: `<token-id-or-tbd>`
- verification artifact: `<path-or-tbd>`

## Rollback Strategy

Define exact rollback steps and blast radius.

## Budget Accounting

Improvement budget category: `<category>`
Audit linkage (PR ID + tier): `<value-or-tbd>`

## Approval Requirements

- [ ] Supervisor approval required before merge
- [ ] HIGH-risk approval token attached (required only for HIGH)
- [ ] Phase acceptance evidence attached before merge

## HALT Discipline

- [ ] HALT entered after proposal creation
- [ ] Explicit authorization required before implementation beyond proposal

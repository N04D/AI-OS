# 08 Security Invariants

## Purpose
Capture invariants that must hold for autonomy execution, governance, dispatch, and audit integrity.

## Current Behavior

### Invariant set
1. No mutation without boundary checks.
2. Capability controls are deny-by-default.
3. Scheduler `guarded_skill` requires explicit capability and budget allowance.
4. Revocation requires governed artifacts and baseline match.
5. Event emission is not mutation authority.
6. Budget deny does not execute guarded task/commit path.
7. Audit artifacts are append-only in operational contract.
8. Phase K ledger chain must verify before replay/inspection outputs.

### Security boundary diagram

```text
[Operator/Automation]
      |
      v
[supervisor.cli] ----> [capability guard] ----> [budget guard] ----> [task/commit boundary]
      |                           |                    |                     |
      |                           |                    |                     +--> deny or apply
      |                           |                    +--> snapshot reason
      |                           +--> emergency deny-list
      +--> scheduler events ----> kernel.events/dispatch ----> plugin runner

Phase K (module): policy + state + ledger chain checks before trust/quota decisions
```

## Fail-Closed Rules
- Invalid permit/policy/state/schema/ledger => deny.
- Missing capability grant => deny.
- Missing/invalid budget state => deny.
- Ledger append/verification failure => deny and stop path.

## Security Boundaries
- `allowed_files` subset check protects governed commit writes.
- Secure execution layer validates permit lineage (`stream_id`, `sequence`, `prev_event_hash`).
- Plugin boundary isolates plugin runtime from core runtime path.

## Determinism Guarantees
- UTC normalization and explicit epoch handling in scheduler/budget modules.
- Canonical JSON hashing in secure layer and Phase K ledger module.
- Stable lexical ordering for scheduler jobs and many list outputs.

## Known Limitations / TODOs
- Phase K integration into runtime authority points is not complete yet.
- Some event timestamps use runtime `now` and are deterministic only as recorded artifacts.

## Cross-links
- [03 Execution Boundary](./03-Execution-Boundary.md)
- [06 Operator Config and Audit](./06-Operator-Config-and-Audit.md)
- [07 Error Code Registry](./07-Error-Code-Registry.md)

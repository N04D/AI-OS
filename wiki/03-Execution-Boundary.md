# 03 Execution Boundary

## Purpose
Document hard execution boundaries for code mutation, permit validation, and deterministic dispatch.

## Current Behavior

### Boundary layers

```text
supervisor/scheduler/guarded_skill -> capability guard -> budget guard -> handler
                                                      \-> deny artifact

supervisor/night_executor -> orchestrator.git.create_governed_commit
                           -> changed_files subset check against allowed_files
                           -> budget check on low_risk_pr_merge
                           -> git add/commit or deterministic deny

executor/dispatch -> secure_execution_layer permit verification
                  -> deterministic command execution scaffold
                  -> append-only audit stream artifacts
```

### Mutation boundary specifics
- `create_governed_commit` denies commits when changed files are outside `dispatch_input.allowed_files`.
- Budget key `low_risk_pr_merge` is consumed before git mutation.
- Deny surfaces include `reason_code`, `budget_key`, `limit`, `used`, `window_start_utc`.

### Secure execution layer specifics
- Execution permits must pass structure + chain checks.
- Replay mode verifies permit and returns deterministic replay metadata.
- Missing/invalid permits trigger kill-switch errors.

## Fail-Closed Rules
- Lock/permit/budget/capability checks deny before mutation.
- Invalid dispatch input or nondeterministic instruction text is rejected.
- Audit stream append violations in secure layer raise kill-switch errors.

## Security Boundaries
- Allowed file subset is enforced at mutation boundary.
- Capability checks and budget checks are additive and cannot self-bypass.
- Secure layer prohibits missing permit execution in live mode.

## Determinism Guarantees
- Deterministic command scaffold in executor dispatch path.
- Stable timestamp formats and canonical JSON for artifacts.
- Replay validation requires exact stream/sequence/prev-hash congruence.

## Known Limitations / TODOs
- Execution scaffold currently uses minimal deterministic command behavior; production behavior remains intentionally constrained.
- Phase K trust/risk quotas are not yet connected to orchestrator commit boundary.

## Cross-links
- [04 Dispatch and Capability Gate](./04-Dispatch-and-Capability-Gate.md)
- [08 Security Invariants](./08-Security-Invariants.md)
- [09 Testing and Verification](./09-Testing-and-Verification.md)

# Run Ledger (JSONL)

The ledger is append-only and tracked in two files:
- `ledger/runs.jsonl`: raw ExecResult-oriented records emitted immediately after task execution.
- `ledger/evaluations.jsonl`: evaluation/commit outcomes keyed by the same `run_id`.

Each evaluation line must include: `run_id`, `task_id`, `evaluation_result`, and `timestamp`.
Each run line (v0.1 minimal) must include:
`version`, `run_id`, `task_id`, `attempt_no`, `env_fingerprint`, `task_spec_hash`, `status`, `stdout`, `stderr`, `ts_start_ms`, and `ts_end_ms`.

## Idempotency rule

`run_id` is the unique key for ingestion.  
If a record with the same `run_id` already exists, ingestion must not append another line and must return the existing record as a duplicate result.

## Exactly-once commit guard

Exactly-once commit is enforced by checking for a ledger record where `run_id` matches and `commit_performed=true`.  
When such a record exists, future commit attempts for that same `run_id` are blocked and treated as rejected.

## Relationship Between Ledgers

`runs.jsonl` captures what happened during execution for a specific `run_id`.  
`evaluations.jsonl` captures what governance decided for that same `run_id` (success/rejection/internal_error).

## Tracking policy

`ledger/evaluations.jsonl` is tracked in git to preserve governed evaluation history.  
`artifacts/*` are ignored because they are ephemeral run outputs and not canonical governance records.

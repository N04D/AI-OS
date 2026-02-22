# Run Ledger (JSONL)

The run ledger is an append-only JSONL file at `ledger/evaluations.jsonl`.
Each line is one evaluation record and must include: `run_id`, `task_id`, `evaluation_result`, and `timestamp`.

## Idempotency rule

`run_id` is the unique key for ingestion.  
If a record with the same `run_id` already exists, ingestion must not append another line and must return the existing record as a duplicate result.

## Exactly-once commit guard

Exactly-once commit is enforced by checking for a ledger record where `run_id` matches and `commit_performed=true`.  
When such a record exists, future commit attempts for that same `run_id` are blocked and treated as rejected.

## Tracking policy

`ledger/evaluations.jsonl` is tracked in git to preserve governed evaluation history.  
`artifacts/*` are ignored because they are ephemeral run outputs and not canonical governance records.

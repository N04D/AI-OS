# Night Executor v0.1

`supervisor/night_executor.py` implements a fail-closed nightly runner that consumes
`governance/night-queue.yaml`, performs preflight checks, writes run/evaluation
records to the governed ledgers, and always emits a compliance report.

## CLI

```bash
python -m supervisor.night_executor --queue governance/night-queue.yaml
```

## Behavior Summary

1. Queue load + schema validation:
   - Parses YAML and requires keys:
     - `mode`
     - `max_tasks`
     - `max_commits`
     - `max_attempts_per_task`
     - `stop_on_first_failure`
     - `allowed_paths`
     - `forbidden_paths`
     - `task_sources`
   - Each `task_sources` entry must include `issue` and `spec`.
   - Any schema error fails closed.

2. Preflight:
   - Requires clean git status (`git status --porcelain` empty).
   - Runs `./scripts/test-all.sh`.
   - Computes `env_fingerprint`:
     - Uses an existing environment fingerprint helper if one is exposed by
       `supervisor.environment_validation`.
     - Otherwise uses deterministic fallback hash of
       `git HEAD sha + OS uname + python version`.

3. Task attempts:
   - `task_id = "issue:<issue>"`
   - `task_spec_hash = sha256(spec file bytes)`
   - `run_id = compute_run_id(task_id, task_spec_hash, env_fingerprint, attempt_no)`
   - Ingests run records via `supervisor.results.ingest_run_record`
     into `ledger/runs.jsonl` (idempotent by `run_id`).
   - Executes through discovered supervisor run-spec entrypoint when present;
     otherwise fail-closed stub returns `rejected` with reason
     `executor_not_wired`.
   - Ingests evaluation records with linkage checks via
     `supervisor.ledger.ingest_evaluation_record_linked`.
   - On success + commit eligible + commit budget remaining, performs governed
     commit and marks run committed with `mark_run_committed`.
   - Honors `stop_on_first_failure`.

## Night Compliance Report

Reports are written to:

`state/night-reports/night-report.<UTC>.json`

Report top-level fields:

- `version`
- `started_at`
- `finished_at`
- `queue_path`
- `queue_mode` (when queue loads successfully)
- `overall_status`
- `preflight`
- `env_fingerprint`
- `entrypoint`
- `summary`
- `tasks`

`summary` fields:

- `tasks_total`
- `tasks_attempted`
- `tasks_succeeded`
- `tasks_failed`
- `commits_performed`
- `errors`

Each `tasks[]` entry includes:

- `task_id`
- `issue`
- `spec`
- `task_spec_hash` (when spec exists)
- `attempts[]`
- `final_status`
- `failure_reason` (when rejected early)

Each `attempts[]` entry includes:

- `attempt_no`
- `run_id`
- `run_status`
- `run_reason`
- `run_ingest_status`
- `evaluation_ingest_status`
- `evaluation_result`
- `commit_eligible`
- `commit_created`
- `commit_sha`

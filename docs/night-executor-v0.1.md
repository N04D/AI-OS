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

2.1 Canonical harness exit-code contract (`scripts/test-all.sh`):
   - `0` => `success`
   - `20` => `git_untrusted`
   - `21` => `git_dirty`
   - `22` => `runner_missing`
   - `23` => `tests_failed`
   - Night preflight records `test_harness_exit_code` and `test_harness_exit_category`.

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
   - Uses `supervisor.night_task_runner.execute_night_task` adapter, which
     calls `supervisor.supervisor.dispatch_task_with_supervisor_permit`
     (Task Execution Engine path) and returns a deterministic structured
     result for every task attempt.

## Night Compliance Report

Reports are written to:

`state/night-reports/night-report.<UTC>.json`

Night mode can place runtime ledgers outside the repository by setting
`LEDGER_DIR` (or `--ledger-dir`), so `runs.jsonl` and `evaluations.jsonl`
do not dirty the git working tree during strict preflight checks.

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

## Secret Handling

Night Executor loads `GITEA_TOKEN` from:
- Environment variable (preferred)
- Fallback file: `/home/infra/.secrets/gitea_token`

`GITEA_BASE_URL` is loaded from the environment variable or fallback file:
- `/home/infra/.secrets/gitea_base_url`

Tokens are never logged or stored in repository.
Missing token causes fail-closed termination.

To run autonomy dry-run safely without modifying queue files:

`./scripts/night-autonomy-dryrun.sh`

This preserves the clean-tree invariant.

## Autonomy Promotion Mode

Queue mode `night-autonomy-promote-v0.1` runs:

1. Preflight checks (clean git tree + test harness).
2. Ledger opportunity analysis and deterministic proposal generation.
3. Deterministic draft PR promotion via `supervisor.autonomy_promotion_gate`.

Promotion gate is fail-closed when:

- `GITEA_TOKEN` is missing.
- the git working tree is dirty.
- a proposal filename hash prefix does not match the proposal content hash.

Branch names are deterministic and derived from `sha256(proposal_content)`.
Existing open PRs for the same deterministic branch are reused (idempotent).

## Autonomy Task Materialization Gate v0.1

`supervisor.autonomy_task_materializer` converts intake-approved autonomy proposal PRs
into deterministic host-side task files:

- Inbox path: `/home/infra/night/state/autonomy/inbox/tasks/<task_id>.json`
- Intake log: `/home/infra/night/state/autonomy/intake-log.jsonl`

Gate checks are fail-closed:

- `GITEA_TOKEN` must be present.
- Git worktree must be clean.
- PR must keep `intake-processed` label.
- PR must have at least one non-bot `APPROVED` review.
- `proposal_hash` in PR body must match the branch hash prefix.
- Existing task-file content mismatch aborts materialization.

CLI groundwork is available through:

`./scripts/aiosctl autonomy materialize`

## Execution Budgeting + Rate Limiter v0.1

Budget gate module: `supervisor.budgets.autonomy` (canonical runtime path)

Host-state files (outside repository):

- `/home/infra/night/state/autonomy/budget.json`
- `/home/infra/night/state/autonomy/budget-log.jsonl`

Windowing and counters are deterministic:

- window = UTC day (`YYYY-MM-DD`)
- stable action keys and limits
- append-only JSONL event log with stable key ordering

Default daily limits:

- `promotion`: 10
- `intake`: 20
- `materialize`: 20
- `exec_attempt`: 30
- `commit`: 5

Default cooldowns:

- `promotion`: 60s
- `intake`: 15s
- `materialize`: 15s
- `exec_attempt`: 5s
- `commit`: 0s

Fail-closed behavior:

- unknown action type -> blocked
- cooldown active -> blocked
- daily limit exhausted -> blocked
- budget state/log I/O failure -> blocked (`budget_internal_error`)

Budget checks are wired into:

- `supervisor.autonomy_promotion_gate` (`promotion`)
- `supervisor.autonomy_review_intake_gate` (`intake`)
- `supervisor.autonomy_task_materializer` (`materialize`)
- `supervisor.night_executor` attempts (`exec_attempt`) and commits (`commit`)

CLI commands:

- `./scripts/aiosctl autonomy budget status`
- `./scripts/aiosctl autonomy budget reset --force`

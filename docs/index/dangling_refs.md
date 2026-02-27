# Dangling References Audit

## Grouped By Missing Path

### docs/*/plugin.yaml
- docs/plugins.md:12 — Discovery target is `*/plugin.yaml`.

### docs/.gitea/governance/path-allowlist.v1.yaml
- docs/gitea-ci-setup.md:45 — - `.gitea/governance/path-allowlist.v1.yaml`
- docs/implementation-plan.v0.1.md:79 — - [ ] Evaluator command runs `scripts/pr_gate_path_allowlist.py` with policy path `.gitea/governance/path-allowlist.v1.yaml`.
- docs/pr-gate-path-allowlist.md:6 — - Policy file: `.gitea/governance/path-allowlist.v1.yaml`
- docs/pr-gate-path-allowlist.md:32 — 3. Loads and evaluates `.gitea/governance/path-allowlist.v1.yaml`

### docs/.gitea/governance/supervisor-capabilities.v1.yaml
- docs/approval-token.md:42 — - `.gitea/governance/supervisor-capabilities.v1.yaml`

### docs/.gitea/workflows/pr-gate.yml
- docs/gitea-ci-setup.md:7 — - File: `.gitea/workflows/pr-gate.yml`
- docs/implementation-plan.v0.1.md:56 — - `.gitea/workflows/pr-gate.yml`
- docs/implementation-plan.v0.1.md:77 — - [ ] `.gitea/workflows/pr-gate.yml` exists and triggers on PR `opened|synchronize|reopened`.

### docs/.github/workflows/pr-gate-path-allowlist.yml
- docs/pr-gate-path-allowlist.md:21 — Workflow file: `.github/workflows/pr-gate-path-allowlist.yml`

### docs/335 passed, 2 warnings in 5.18s
- docs/governance-invariants.v0.2.md:4 — - Exact pytest summary: `335 passed, 2 warnings in 5.18s`

### docs/NIGHT_BRANCH=dev ./scripts/night-bootstrap.sh
- docs/night-mode.v0.1.md:10 — Example: `NIGHT_BRANCH=dev ./scripts/night-bootstrap.sh`

### docs/Specifications AI-OS/.gitea/pull_request_template.md
- docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:357 — 3. Add PR template in `.gitea/pull_request_template.md` (or repo equivalent)

### docs/Specifications AI-OS/All governance gates satisfied (policy v0.2, hash …
- docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:349 — * **PASS:** `All governance gates satisfied (policy v0.2, hash …)`

### docs/Specifications AI-OS/artifacts/governance/pr-<num>-<headsha>.json
- docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:246 — `artifacts/governance/pr-<num>-<headsha>.json`

### docs/Specifications AI-OS/environment.json
- docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:320 — * The Supervisor should derive `owner/repo` dynamically from `environment.json` or git remote (aligns with your backlog item: remove hard-coded owner/repo).

### docs/Specifications AI-OS/git log --show-signature <base>..<head
- docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:166 — * `git log --show-signature <base>..<head>`

### docs/agents/state/environment.json
- docs/governance.md:78 — `agents/state/environment.json`. Refer to those files for details.)
- docs/supervisor-governance-enforcement-v0.1.md:47 — `docs/governance.md` and `agents/state/environment.json`

### docs/approvals/capabilities/revoke/<revoke_id>.approved
- docs/supervisor-autonomy.v0.2.md:13 — - Requires approval marker at `approvals/capabilities/revoke/<revoke_id>.approved`.

### docs/archive/conceptual/agents/state/environment.json
- docs/archive/conceptual/daily-autonomous-execution-protocol-v0.1.md:74 — - Configured in `agents/state/environment.json`

### docs/archive/governance_versions/KillSwitchError.code
- docs/archive/governance_versions/governance-invariants.v0.1.md:25 — - `KillSwitchError.code` compatibility contract is restored and covered by tests.

### docs/archive/governance_versions/commit_signing.accepted_types
- docs/archive/governance_versions/governance-invariants.v0.1.md:16 — - `commit_signing.accepted_types` is enforced.

### docs/archive/governance_versions/commit_signing.mode
- docs/archive/governance_versions/governance-invariants.v0.1.md:15 — - `commit_signing.mode` is enforced.

### docs/archive/governance_versions/gate-verdict.json
- docs/archive/governance_versions/governance-invariants.v0.1.md:11 — - `gate-verdict.json` is machine-readable.

### docs/archive/governance_versions/governance-policy-sha.txt
- docs/archive/governance_versions/governance-invariants.v0.1.md:35 — - Effective policy SHA anchor is recorded in [docs/governance-policy-sha.txt](./governance-policy-sha.txt).

### docs/archive/governance_versions/requirements-dev.txt
- docs/archive/governance_versions/governance-invariants.v0.1.md:30 — - `requirements-dev.txt` is pinned.

### docs/archive/governance_versions/requirements.txt
- docs/archive/governance_versions/governance-invariants.v0.1.md:29 — - `requirements.txt` is pinned.

### docs/bash scripts/test-pr-gate-m1.sh
- docs/implementation-plan.v0.1.md:83 — - `bash scripts/test-pr-gate-m1.sh`

### docs/body.payload
- docs/approval-token.md:35 — - `body.payload` if present

### docs/channel-boundaries.v0.1.md
- docs/implementation-plan.v0.1.md:120 — - `docs/channel-boundaries.v0.1.md`

### docs/channels/channel.telegram.message
- docs/channels/telegram.v0.1.md:6 — `channel.telegram.message`.

### docs/channels/logs/control/channel-telegram.jsonl
- docs/channels/telegram.v0.1.md:29 — - `logs/control/channel-telegram.jsonl`
- docs/channels/telegram.v0.1.md:42 — - `AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH` (default: `logs/control/channel-telegram.jsonl`)

### docs/channels/logs/control/kernel-events.jsonl
- docs/channels/telegram.v0.1.md:32 — - `logs/control/kernel-events.jsonl`
- docs/channels/telegram.v0.1.md:41 — - `AIOS_EVENT_AUDIT_LOG_PATH` (default: `logs/control/kernel-events.jsonl`)

### docs/config.json
- docs/plugins-ops.md:11 — `config.json` is operator-owned enablement state.
- docs/plugins-ops.md:15 — - `config.json` canonical shape:
- docs/plugins-ops.md:19 — Canonical `config.json`:

### docs/dark.png
- docs/Specifications AI-OS/.obsidian/themes/flexcyon/manifest.json:6 — "screenshot": "./docs/dark.png",

### docs/error.details[0
- docs/dispatch-api.v0.1.md:64 — Runner reason codes are preserved in `error.details[0]`.

### docs/evaluations.jsonl
- docs/night-executor-v0.1.md:71 — `LEDGER_DIR` (or `--ledger-dir`), so `runs.jsonl` and `evaluations.jsonl`

### docs/execution.out_of_process: true
- docs/plugins.md:52 — Plugins are out-of-process (`execution.out_of_process: true`) and may not modify kernel or runtime internals.

### docs/executor/dispatch.py
- docs/governance-commit-policy-regex-fix-v0.1.md:83 — - `executor/dispatch.py`

### docs/gate-verdict.json
- docs/gitea-ci-setup.md:53 — - `gate-verdict.json`
- docs/gitea-ci-setup.md:77 — Workflow always emits `gate-verdict.json` and prints it in logs via the `Emit gate verdict` step.
- docs/implementation-plan.v0.1.md:68 — - `gate-verdict.json` generated in CI run workspace.
- docs/implementation-plan.v0.1.md:80 — - [ ] Workflow emits `gate-verdict.json` and fails closed on missing token/API base/evaluator error.
- docs/pr-gate-path-allowlist.md:33 — 4. Writes `gate-verdict.json`
- docs/pr-gate-path-allowlist.md:34 — 5. Uploads `gate-verdict.json` as workflow artifact
- docs/pr-gate-path-allowlist.md:38 — The evaluator writes `gate-verdict.json`:

### docs/hardening/TLSv1.2
- docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:15 — - TLS downgrade: HTTP traffic is redirected to HTTPS and TLS is restricted to `TLSv1.2`/`TLSv1.3`.

### docs/hardening/TLSv1.3
- docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:15 — - TLS downgrade: HTTP traffic is redirected to HTTPS and TLS is restricted to `TLSv1.2`/`TLSv1.3`.

### docs/hardening/app/logs/control/channel-telegram.jsonl
- docs/hardening/container-hardening.v0.1.md:68 — - `AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH` (default `/app/logs/control/channel-telegram.jsonl`)

### docs/hardening/app/logs/control/kernel-events.jsonl
- docs/hardening/container-hardening.v0.1.md:67 — - `AIOS_EVENT_AUDIT_LOG_PATH` (default `/app/logs/control/kernel-events.jsonl`)

### docs/hardening/app/state/plugins/config.json
- docs/hardening/container-hardening.v0.1.md:66 — - `AIOS_CONFIG_PATH` (default `/app/state/plugins/config.json`)

### docs/hardening/app/state/plugins/registry.json
- docs/hardening/container-hardening.v0.1.md:65 — - `AIOS_REGISTRY_PATH` (default `/app/state/plugins/registry.json`)

### docs/hardening/docker/Dockerfile.webhook
- docs/hardening/container-hardening.v0.1.md:27 — - `docker/Dockerfile.webhook`

### docs/hardening/docker/docker-compose.yml
- docs/hardening/container-hardening.v0.1.md:28 — - `docker/docker-compose.yml`

### docs/hardening/docker/nginx/aios-telegram.conf
- docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:22 — - `docker/nginx/aios-telegram.conf`

### docs/hardening/docker/nginx/nginx.conf
- docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:21 — - `docker/nginx/nginx.conf`

### docs/hardening/etc/letsencrypt/live/your-domain.com/fullchain.pem
- docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:71 — - `/etc/letsencrypt/live/your-domain.com/fullchain.pem`

### docs/hardening/etc/letsencrypt/live/your-domain.com/privkey.pem
- docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:72 — - `/etc/letsencrypt/live/your-domain.com/privkey.pem`

### docs/home/infra/night/state/autonomy/approval-replay.sqlite3
- docs/approval-token.md:77 — - default `/home/infra/night/state/autonomy/approval-replay.sqlite3`

### docs/home/infra/night/state/autonomy/budget-log.jsonl
- docs/night-executor-v0.1.md:183 — - `/home/infra/night/state/autonomy/budget-log.jsonl`

### docs/home/infra/night/state/autonomy/budget.json
- docs/night-executor-v0.1.md:182 — - `/home/infra/night/state/autonomy/budget.json`

### docs/home/infra/night/state/autonomy/inbox/tasks/<task_id>.json
- docs/night-executor-v0.1.md:160 — - Inbox path: `/home/infra/night/state/autonomy/inbox/tasks/<task_id>.json`

### docs/home/infra/night/state/autonomy/intake-log.jsonl
- docs/night-executor-v0.1.md:161 — - Intake log: `/home/infra/night/state/autonomy/intake-log.jsonl`

### docs/kernel.dispatch.dispatch(
- docs/event-bus.v0.1.md:4 — Provide an internal-only event fan-out API that routes kernel events to enabled plugins through `kernel.dispatch.dispatch()`.

### docs/kernel/plugins/runner.py
- docs/dispatch-api.v0.1.md:9 — - Uses secure runner: `kernel/plugins/runner.py`

### docs/ledger/runs.jsonl
- docs/night-executor-v0.1.md:50 — into `ledger/runs.jsonl` (idempotent by `run_id`).

### docs/logs/control/kernel-events.jsonl
- docs/event-bus.v0.1.md:52 — - Audit file: `logs/control/kernel-events.jsonl`.

### docs/logs/control/plugin-events.jsonl
- docs/plugins-ops.md:54 — - Append-only JSONL: `logs/control/plugin-events.jsonl`

### docs/night-autonomy-promote-v0.1
- docs/night-executor-v0.1.md:140 — Queue mode `night-autonomy-promote-v0.1` runs:

### docs/plugin.yaml
- docs/plugins.md:38 — Official plugins must have `signing.registry_signed: true` in `plugin.yaml`.

### docs/plugins-boundary.v0.1.md
- docs/implementation-plan.v0.1.md:94 — - `docs/plugins-boundary.v0.1.md`

### docs/plugins.{plugin_id}.enabled == true
- docs/event-bus.v0.1.md:47 — - `plugins.{plugin_id}.enabled == true`

### docs/python scripts/aios_plugins.py disable <plugin_id
- docs/plugins-ops.md:45 — - `python scripts/aios_plugins.py disable <plugin_id>`

### docs/python scripts/aios_plugins.py enable <plugin_id
- docs/plugins-ops.md:44 — - `python scripts/aios_plugins.py enable <plugin_id>`

### docs/python scripts/aios_plugins.py list
- docs/plugins-ops.md:43 — - `python scripts/aios_plugins.py list`

### docs/python scripts/aios_plugins.py set-unsafe-external true|false
- docs/plugins-ops.md:46 — - `python scripts/aios_plugins.py set-unsafe-external true|false`

### docs/python3 -m py_compile supervisor/governance_enforcement.py
- docs/governance-commit-policy-regex-fix-v0.1.md:78 — 1) `python3 -m py_compile supervisor/governance_enforcement.py`

### docs/registry.json
- docs/plugins-ops.md:10 — `registry.json` is discovery output. It is read-only for operators.
- docs/plugins-ops.md:14 — - `registry.json` contains discovered plugin metadata (`plugin_id`, `version`, `trust_tier`, `path`, `fingerprint`, `api_version`).
- docs/plugins-ops.md:41 — 1. Refresh discovery into `registry.json`.

### docs/requests/capabilities/revoke/<timestamp>__<capability>__<reason_slug>.json
- docs/supervisor-autonomy.v0.2.md:8 — - Writes revoke request artifact at `requests/capabilities/revoke/<timestamp>__<capability>__<reason_slug>.json`.

### docs/roadmap/*.json
- docs/roadmap/codex_autonomy_roadmap.md:458 — - [x] Step 1: Add deterministic local intake source from `state/issues/open/*.md` and `*.json`.

### docs/roadmap/422 passed, 14 skipped in 23.67s
- docs/roadmap/codex_autonomy_progress.md:421 — - `422 passed, 14 skipped in 23.67s` (`pytest -q`)

### docs/roadmap/428 passed, 14 skipped in 27.36s
- docs/roadmap/codex_autonomy_progress.md:465 — - full suite: `428 passed, 14 skipped in 27.36s` (`pytest -q`)

### docs/roadmap/431 passed, 14 skipped in 27.04s
- docs/roadmap/codex_autonomy_progress.md:501 — - full suite: `431 passed, 14 skipped in 27.04s` (`pytest -q`)

### docs/roadmap/autonomy_orchestrator/night_mode.py
- docs/roadmap/codex_autonomy_progress.md:170 — - `autonomy_orchestrator/night_mode.py`
- docs/roadmap/codex_autonomy_progress.md:189 — - night mode pre-execution flow (`autonomy_orchestrator/night_mode.py`)
- docs/roadmap/codex_autonomy_roadmap.md:484 — - [x] Confirmed runtime gate is HIGH-only in `autonomy_orchestrator/night_mode.py` (`is_self_improvement and risk_tier == "HIGH"`).

### docs/roadmap/determinism_evidence.json
- docs/roadmap/codex_autonomy_roadmap.md:242 — - [x] Define `determinism_evidence.json` schema.

### docs/roadmap/helloworld.txt
- docs/roadmap/codex_autonomy_roadmap.md:466 — - [x] Step 9: Add positive test: hello-world local issue creates `helloworld.txt` via governed flow.

### docs/roadmap/home/infra/AI-OS/governance_policy.yaml
- docs/roadmap/codex_autonomy_progress.md:94 — - Phase-K budget tests require `/home/infra/AI-OS/governance_policy.yaml`

### docs/roadmap/logs/control/approval_token_audit.jsonl
- docs/roadmap/codex_autonomy_progress.md:129 — - SHA256 token hash logging added to audit stream (`logs/control/approval_token_audit.jsonl`)

### docs/roadmap/logs/control/interrupts/<date>/interrupt__<checkpoint>.json
- docs/roadmap/codex_autonomy_progress.md:153 — - `logs/control/interrupts/<date>/interrupt__<checkpoint>.json`

### docs/roadmap/orchestrator/commit_flow.py
- docs/roadmap/codex_autonomy_progress.md:20 — - `orchestrator/commit_flow.py` (passes explicit changed file list)

### docs/roadmap/orchestrator/git.py
- docs/roadmap/codex_autonomy_progress.md:14 — - `orchestrator/git.py`
- docs/roadmap/codex_autonomy_progress.md:19 — - `orchestrator/git.py` (`commit()` now stages explicit files)
- docs/roadmap/codex_autonomy_progress.md:171 — - `orchestrator/git.py`

### docs/roadmap/requests/capabilities/night_mode/<epoch>__issue_<id>__<task_hash>.json
- docs/roadmap/codex_autonomy_progress.md:440 — - `requests/capabilities/night_mode/<epoch>__issue_<id>__<task_hash>.json`

### docs/roadmap/supervisor.autonomy_budget
- docs/roadmap/autonomy_budget_gate_redundancy_proof.md:24 — - `supervisor/night_executor.py` budget checks now route through `supervisor.autonomy_budget`.
- docs/roadmap/codex_autonomy_progress.md:33 — - `supervisor/night_executor.py` now uses `supervisor.autonomy_budget` via a compatibility adapter (`check_and_consume`)
- docs/roadmap/codex_autonomy_progress.md:61 — - no production imports remain for `supervisor.autonomy_budget` or `supervisor.autonomy_budget_gate`

### docs/roadmap/supervisor.autonomy_budget_gate
- docs/roadmap/autonomy_budget_gate_redundancy_proof.md:25 — - No production import of `supervisor.autonomy_budget_gate` remains.
- docs/roadmap/codex_autonomy_progress.md:34 — - removed direct runtime dependency on `supervisor.autonomy_budget_gate` internals
- docs/roadmap/codex_autonomy_progress.md:61 — - no production imports remain for `supervisor.autonomy_budget` or `supervisor.autonomy_budget_gate`

### docs/roadmap/supervisor.budgets.autonomy
- docs/roadmap/codex_autonomy_progress.md:44 — - updated runtime and gate imports to `supervisor.budgets.autonomy`

### docs/roadmap/sys.executable
- docs/roadmap/codex_autonomy_progress.md:103 — - plugin-loader tests now use `sys.executable` (environment-agnostic process launch)
- docs/roadmap/codex_autonomy_roadmap.md:83 — - [x] Remediation 1: Normalize plugin-loader tests to environment Python (`sys.executable`)

### docs/roadmap/tests/test_aiosctl_scheduler_tick.py
- docs/roadmap/codex_autonomy_progress.md:156 — - `tests/test_aiosctl_scheduler_tick.py` (scheduler tick interrupt halt)
- docs/roadmap/codex_autonomy_progress.md:158 — - targeted run: `25 passed` (`tests/test_night_mode.py`, `tests/test_aiosctl_scheduler_tick.py`)

### docs/roadmap/tests/test_aiosctl_scheduler_tick.py::test_scheduler_tick_denies_when_budget_state_is_tampered
- docs/roadmap/codex_autonomy_progress.md:197 — - `tests/test_aiosctl_scheduler_tick.py::test_scheduler_tick_denies_when_budget_state_is_tampered`

### docs/roadmap/tests/test_git_remote.py
- docs/roadmap/codex_autonomy_progress.md:51 — - `tests/test_git_remote.py`

### docs/roadmap/tests/test_mutation_boundary.py
- docs/roadmap/codex_autonomy_progress.md:22 — - `tests/test_mutation_boundary.py`

### docs/roadmap/tests/test_night_mode.py
- docs/roadmap/codex_autonomy_progress.md:86 — - No governance bypass possible: covered by existing fail-closed tests in `tests/test_night_mode.py` (`DENY_*` paths).
- docs/roadmap/codex_autonomy_progress.md:89 — - Targeted Phase 2 suite: `29 passed` (`tests/test_night_mode.py`, scheduler, budget suites).
- docs/roadmap/codex_autonomy_progress.md:90 — - `tests/test_night_mode.py`: `20 passed`.
- docs/roadmap/codex_autonomy_progress.md:155 — - `tests/test_night_mode.py` (phase-boundary + pre-budget interrupt halt)
- docs/roadmap/codex_autonomy_progress.md:158 — - targeted run: `25 passed` (`tests/test_night_mode.py`, `tests/test_aiosctl_scheduler_tick.py`)
- docs/roadmap/codex_autonomy_progress.md:453 — - `tests/test_night_mode.py`
- docs/roadmap/codex_autonomy_progress.md:464 — - targeted suite: `29 passed` (`tests/test_night_mode.py`)
- docs/roadmap/codex_autonomy_progress.md:500 — - `tests/test_night_mode.py`

### docs/roadmap/tests/test_night_mode.py::test_identical_output_for_identical_state
- docs/roadmap/codex_autonomy_progress.md:79 — - `tests/test_night_mode.py::test_identical_output_for_identical_state`

### docs/roadmap/tests/test_night_mode.py::test_night_mode_denies_on_budget_state_tamper
- docs/roadmap/codex_autonomy_progress.md:196 — - `tests/test_night_mode.py::test_night_mode_denies_on_budget_state_tamper`

### docs/roadmap/tests/test_night_mode.py::test_summary_has_only_controlled_time_field
- docs/roadmap/codex_autonomy_progress.md:80 — - `tests/test_night_mode.py::test_summary_has_only_controlled_time_field`

### docs/roadmap/tests/test_night_mode.py::test_three_consecutive_night_runs_succeed
- docs/roadmap/codex_autonomy_progress.md:78 — - `tests/test_night_mode.py::test_three_consecutive_night_runs_succeed`

### docs/roadmap/tests/test_night_mode_local_intake.py
- docs/roadmap/codex_autonomy_progress.md:499 — - `tests/test_night_mode_local_intake.py`

### docs/roadmap/tests/test_night_mode_local_intake.py::test_local_email_issue_missing_capability_emits_request_and_denies
- docs/roadmap/codex_autonomy_progress.md:493 — - `tests/test_night_mode_local_intake.py::test_local_email_issue_missing_capability_emits_request_and_denies`

### docs/roadmap/tests/test_night_mode_local_intake.py::test_local_hello_world_issue_creates_file_and_halts
- docs/roadmap/codex_autonomy_progress.md:491 — - `tests/test_night_mode_local_intake.py::test_local_hello_world_issue_creates_file_and_halts`

### docs/roadmap/tests/test_night_mode_local_intake.py::test_local_queue_recheck_processes_in_order_and_halts_when_empty
- docs/roadmap/codex_autonomy_progress.md:495 — - `tests/test_night_mode_local_intake.py::test_local_queue_recheck_processes_in_order_and_halts_when_empty`

### docs/roadmap/tests/test_orchestrator_git_remote.py
- docs/roadmap/codex_autonomy_progress.md:52 — - `tests/test_orchestrator_git_remote.py`

### docs/roadmap/tests/test_self_improvement_boundary_scan.py
- docs/roadmap/codex_autonomy_progress.md:270 — - `tests/test_self_improvement_boundary_scan.py`
- docs/roadmap/codex_autonomy_progress.md:290 — - `tests/test_self_improvement_boundary_scan.py`
- docs/roadmap/codex_autonomy_progress.md:358 — - targeted suites: `16 passed` (`tests/test_self_improvement_pipeline.py`, `tests/test_self_improvement_boundary_scan.py`)

### docs/roadmap/tests/test_self_improvement_pipeline.py
- docs/roadmap/codex_autonomy_progress.md:242 — - `tests/test_self_improvement_pipeline.py`
- docs/roadmap/codex_autonomy_progress.md:289 — - `tests/test_self_improvement_pipeline.py`
- docs/roadmap/codex_autonomy_progress.md:351 — - `tests/test_self_improvement_pipeline.py`
- docs/roadmap/codex_autonomy_progress.md:358 — - targeted suites: `16 passed` (`tests/test_self_improvement_pipeline.py`, `tests/test_self_improvement_boundary_scan.py`)
- docs/roadmap/codex_autonomy_progress.md:390 — - extended tests in `tests/test_self_improvement_pipeline.py`:

### docs/roadmap/tests/test_self_improvement_pipeline.py:153
- docs/roadmap/codex_autonomy_progress.md:408 — - `tests/test_self_improvement_pipeline.py:153`

### docs/roadmap/tests/test_self_improvement_pipeline.py:517
- docs/roadmap/codex_autonomy_progress.md:411 — - `tests/test_self_improvement_pipeline.py:517`

### docs/roadmap/tests/test_self_improvement_pipeline.py:631
- docs/roadmap/codex_autonomy_progress.md:414 — - `tests/test_self_improvement_pipeline.py:631`

### docs/roadmap/tests/test_state_json_determinism.py
- docs/roadmap/codex_autonomy_progress.md:24 — - `tests/test_state_json_determinism.py`

### docs/roadmap/tests/test_supervisor_boundary_imports.py
- docs/roadmap/codex_autonomy_progress.md:173 — - `tests/test_supervisor_boundary_imports.py`

### docs/roadmap/tests/test_utc_enforcement.py
- docs/roadmap/codex_autonomy_progress.md:49 — - `tests/test_utc_enforcement.py`

### docs/runs.jsonl
- docs/night-executor-v0.1.md:71 — `LEDGER_DIR` (or `--ledger-dir`), so `runs.jsonl` and `evaluations.jsonl`

### docs/runtime.timeout_seconds
- docs/ipc-runner.v0.1.md:37 — - `runtime.timeout_seconds` must be present and > 0.

### docs/scheduler.job_due
- docs/supervisor-autonomy.v0.2.md:60 — - Emits `scheduler.job_due` events in lexical `job_id` order.

### docs/script/test-all.sh
- docs/night-mode.v0.1.md:11 — For compatibility across repositories, harness discovery supports `./scripts/test-all.sh` first and `./script/test-all.sh` as fallback.

### docs/scripts/night-autonomy-dryrun.sh
- docs/night-executor-v0.1.md:134 — `./scripts/night-autonomy-dryrun.sh`

### docs/scripts/test-all.sh
- docs/night-executor-v0.1.md:30 — - Runs `./scripts/test-all.sh`.
- docs/night-mode.v0.1.md:8 — The script ensures the Night workspace is a clean clone/reset state and that `./scripts/test-all.sh` passes in that workspace.
- docs/night-mode.v0.1.md:11 — For compatibility across repositories, harness discovery supports `./scripts/test-all.sh` first and `./script/test-all.sh` as fallback.

### docs/signing.registry_signed: true
- docs/plugins.md:38 — Official plugins must have `signing.registry_signed: true` in `plugin.yaml`.

### docs/skill-boundaries.v0.1.md
- docs/implementation-plan.v0.1.md:143 — - `docs/skill-boundaries.v0.1.md`

### docs/skills/channels.<id>.quotas.per_user_per_hour
- docs/skills/skills.v0.1.md:98 — 5. Quota enforcement (`channels.<id>.quotas.per_user_per_hour`)

### docs/skills/kernel.dispatch
- docs/skills/skills.v0.1.md:4 — The Skills Mediation Layer sits above `kernel.dispatch` and enforces deny-by-default authorization for external channels before any plugin method invocation.

### docs/skills/python -m unittest -v tests.test_skills_policy
- docs/skills/skills.v0.1.md:128 — - `python -m unittest -v tests.test_skills_policy`

### docs/skills/rate_limit.cooldown_seconds
- docs/skills/skills.v0.1.md:97 — 4. Cooldown enforcement (`rate_limit.cooldown_seconds`)

### docs/skills/result.ok == true
- docs/skills/skills.v0.1.md:105 — - Cooldown state is updated only after successful dispatch (`result.ok == true`).

### docs/specs/determinism_evidence.json
- docs/specs/self_improvement_proposal.v0.1.md:58 — - `determinism_evidence.json`: `<path-or-tbd>`

### docs/specs/event_type = "permit.issued
- docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md:58 — - `event_type = "permit.issued"`.

### docs/specs/event_type=permit.issued
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:31 — - issuance audit event proposal (`event_type=permit.issued`)

### docs/specs/review_ref.review_id
- docs/specs/execution-permit-attestation-contract-v0.1.md:93 — - `review_ref.review_id`

### docs/specs/review_ref.review_type
- docs/specs/execution-permit-attestation-contract-v0.1.md:94 — - `review_ref.review_type`

### docs/specs/secure_execution_layer.execution_permit.v1
- docs/specs/execution-permit-attestation-contract-v0.1.md:25 — - `secure_execution_layer.execution_permit.v1`
- docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md:55 — - Domain: `secure_execution_layer.execution_permit.v1`.

### docs/specs/secure_layer.enforce.ambiguous_mapping
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:81 — - `secure_layer.enforce.ambiguous_mapping`

### docs/specs/secure_layer.enforce.chain_mismatch
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:78 — - `secure_layer.enforce.chain_mismatch`

### docs/specs/secure_layer.enforce.invalid_permit
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:77 — - `secure_layer.enforce.invalid_permit`

### docs/specs/secure_layer.enforce.policy_mismatch
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:79 — - `secure_layer.enforce.policy_mismatch`

### docs/specs/secure_layer.enforce.replay_mismatch
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:83 — - `secure_layer.enforce.replay_mismatch`

### docs/specs/secure_layer.enforce.review_missing
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:80 — - `secure_layer.enforce.review_missing`

### docs/specs/secure_layer.enforce.unbound_request
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:82 — - `secure_layer.enforce.unbound_request`

### docs/subscriptions: ["event.a", "event.b"
- docs/event-bus.v0.1.md:39 — - `subscriptions: ["event.a", "event.b"]`

### docs/supervisor.autonomy_promotion_gate
- docs/night-executor-v0.1.md:144 — 3. Deterministic draft PR promotion via `supervisor.autonomy_promotion_gate`.
- docs/night-executor-v0.1.md:216 — - `supervisor.autonomy_promotion_gate` (`promotion`)

### docs/supervisor.autonomy_review_intake_gate
- docs/night-executor-v0.1.md:217 — - `supervisor.autonomy_review_intake_gate` (`intake`)

### docs/supervisor.autonomy_task_materializer
- docs/night-executor-v0.1.md:157 — `supervisor.autonomy_task_materializer` converts intake-approved autonomy proposal PRs
- docs/night-executor-v0.1.md:218 — - `supervisor.autonomy_task_materializer` (`materialize`)

### docs/supervisor.budgets.autonomy
- docs/night-executor-v0.1.md:178 — Budget gate module: `supervisor.budgets.autonomy` (canonical runtime path)

### docs/supervisor.environment_validation
- docs/night-executor-v0.1.md:33 — `supervisor.environment_validation`.

### docs/supervisor.ledger.ingest_evaluation_record_linked
- docs/night-executor-v0.1.md:55 — `supervisor.ledger.ingest_evaluation_record_linked`.

### docs/supervisor.night_executor
- docs/night-executor-v0.1.md:219 — - `supervisor.night_executor` attempts (`exec_attempt`) and commits (`commit`)

### docs/supervisor.night_task_runner.execute_night_task
- docs/night-executor-v0.1.md:59 — - Uses `supervisor.night_task_runner.execute_night_task` adapter, which

### docs/supervisor.results.ingest_run_record
- docs/night-executor-v0.1.md:49 — - Ingests run records via `supervisor.results.ingest_run_record`

### docs/supervisor.supervisor.dispatch_task_with_supervisor_permit
- docs/night-executor-v0.1.md:60 — calls `supervisor.supervisor.dispatch_task_with_supervisor_permit`

### docs/system-ops-executor.v0.1.md
- docs/implementation-plan.v0.1.md:189 — - `docs/system-ops-executor.v0.1.md`

### docs/tests/test_gateway_boundary.py
- docs/implementation-plan.v0.1.md:121 — - `tests/test_gateway_boundary.py`

### docs/tests/test_plugin_boundary_validator.py
- docs/implementation-plan.v0.1.md:96 — - `tests/test_plugin_boundary_validator.py`

### docs/tests/test_plugin_loader.py
- docs/implementation-plan.v0.1.md:95 — - `tests/test_plugin_loader.py`

### docs/tests/test_pr_gate_gitea_workflow.py
- docs/implementation-plan.v0.1.md:58 — - `tests/test_pr_gate_gitea_workflow.py` (integration/contract test)

### docs/tests/test_skill_framework.py
- docs/implementation-plan.v0.1.md:144 — - `tests/test_skill_framework.py`

### docs/tests/test_system_ops_executor.py
- docs/implementation-plan.v0.1.md:190 — - `tests/test_system_ops_executor.py`

### docs/tests/test_user_policy_validation.py
- docs/implementation-plan.v0.1.md:167 — - `tests/test_user_policy_validation.py`

### docs/token = base64url(payload_json) + "." + base64url(hmac_sha256(APPROVAL_SECRET, base64url(payload_json))
- docs/approval-token.md:7 — `token = base64url(payload_json) + "." + base64url(hmac_sha256(APPROVAL_SECRET, base64url(payload_json)))`

### docs/user-governance-ui.v0.1.md
- docs/implementation-plan.v0.1.md:166 — - `docs/user-governance-ui.v0.1.md`

### docs/v0.1
- docs/phase-acceptance-rule.v0.1.md:19 — - `version` (must be `v0.1`)

### docs/{"id":"<uuid>","ok":true|false,...}
- docs/plugins.md:71 — - `{"id":"<uuid>","ok":true|false,...}`

### docs/{"type":"request","id":"<uuid>","capability":"notify:escalation","payload":{...}}
- docs/plugins.md:69 — - `{"type":"request","id":"<uuid>","capability":"notify:escalation","payload":{...}}`

### governance/path-allowlist.v1.yaml
- docs/gitea-ci-setup.md:45 — - `.gitea/governance/path-allowlist.v1.yaml`
- docs/implementation-plan.v0.1.md:79 — - [ ] Evaluator command runs `scripts/pr_gate_path_allowlist.py` with policy path `.gitea/governance/path-allowlist.v1.yaml`.
- docs/pr-gate-path-allowlist.md:6 — - Policy file: `.gitea/governance/path-allowlist.v1.yaml`
- docs/pr-gate-path-allowlist.md:32 — 3. Loads and evaluates `.gitea/governance/path-allowlist.v1.yaml`

### governance/reviews/<review_id>.review.json
- docs/specs/controlled-runtime-enforcement-plan-v0.1.md:106 — - resume requires Git-visible `governance/reviews/<review_id>.review.json`
- docs/specs/execution-permit-attestation-contract-v0.1.md:102 — - `governance/reviews/<review_id>.review.json` MUST exist in the evaluated Git state.
- docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md:80 — 2. Verify `governance/reviews/<review_id>.review.json` exists in evaluated Git state.

### governance/supervisor-capabilities.v1.yaml
- docs/approval-token.md:42 — - `.gitea/governance/supervisor-capabilities.v1.yaml`

### state/active_phase.json
- docs/phase-gate-governance-protocol-v0.1.md:152 — agents/state/active_phase.json

### state/autonomy/approval-replay.sqlite3
- docs/approval-token.md:77 — - default `/home/infra/night/state/autonomy/approval-replay.sqlite3`

### state/autonomy/budget-log.jsonl
- docs/night-executor-v0.1.md:183 — - `/home/infra/night/state/autonomy/budget-log.jsonl`

### state/autonomy/budget.json
- docs/night-executor-v0.1.md:182 — - `/home/infra/night/state/autonomy/budget.json`

### state/autonomy/intake-log.jsonl
- docs/night-executor-v0.1.md:161 — - Intake log: `/home/infra/night/state/autonomy/intake-log.jsonl`

### state/capability_requests/<epoch>__<issue_id>__<capability>.json
- docs/roadmap/codex_autonomy_progress.md:486 — - `state/capability_requests/<epoch>__<issue_id>__<capability>.json`

### state/environment.json
- docs/archive/conceptual/daily-autonomous-execution-protocol-v0.1.md:74 — - Configured in `agents/state/environment.json`
- docs/evaluation-and-commit-protocol-v0.1.md:114 — agents/state/environment.json
- docs/governance.md:78 — `agents/state/environment.json`. Refer to those files for details.)
- docs/pre-execution-environment-validation-v0.1.md:115 — agents/state/environment.json
- docs/supervisor-governance-enforcement-v0.1.md:47 — `docs/governance.md` and `agents/state/environment.json`

### state/issues/open/*.json
- docs/roadmap/codex_autonomy_progress.md:475 — - `state/issues/open/*.json`

### state/issues/open/*.md
- docs/roadmap/codex_autonomy_progress.md:476 — - `state/issues/open/*.md`
- docs/roadmap/codex_autonomy_roadmap.md:458 — - [x] Step 1: Add deterministic local intake source from `state/issues/open/*.md` and `*.json`.

### state/issues/open/901-high-star.json
- docs/roadmap/codex_autonomy_roadmap.md:483 — - [x] Diagnosed `DENY_TOKEN_MISSING` on user machine as HIGH-risk input issue (`state/issues/open/901-high-star.json`), not branch mismatch.

### state/night-reports/night-report.<UTC>.json
- docs/night-executor-v0.1.md:68 — `state/night-reports/night-report.<UTC>.json`

### state/plugins/config.json
- docs/channels/telegram.v0.1.md:40 — - `AIOS_CONFIG_PATH` (default: `state/plugins/config.json`)
- docs/dispatch-api.v0.1.md:19 — `dispatch(plugin_id, method, payload, *, request_id=None, registry_path="state/plugins/registry.json", config_path="state/plugins/config.json", audit_log_path="logs/control/plugin-runtime.jsonl", runner_state_dir_base="state/plugins/runtime", timeout_override_seconds=None) -> dict`
- docs/event-bus.v0.1.md:19 — config_path="state/plugins/config.json",
- docs/hardening/container-hardening.v0.1.md:66 — - `AIOS_CONFIG_PATH` (default `/app/state/plugins/config.json`)
- docs/plugins-ops.md:8 — - Operator config: `state/plugins/config.json`
- docs/skills/skills.v0.1.md:85 — config_path="state/plugins/config.json",

### state/plugins/registry.json
- docs/channels/telegram.v0.1.md:39 — - `AIOS_REGISTRY_PATH` (default: `state/plugins/registry.json`)
- docs/dispatch-api.v0.1.md:19 — `dispatch(plugin_id, method, payload, *, request_id=None, registry_path="state/plugins/registry.json", config_path="state/plugins/config.json", audit_log_path="logs/control/plugin-runtime.jsonl", runner_state_dir_base="state/plugins/runtime", timeout_override_seconds=None) -> dict`
- docs/event-bus.v0.1.md:18 — registry_path="state/plugins/registry.json",
- docs/hardening/container-hardening.v0.1.md:65 — - `AIOS_REGISTRY_PATH` (default `/app/state/plugins/registry.json`)
- docs/plugins-ops.md:7 — - Registry: `state/plugins/registry.json`
- docs/plugins.md:23 — - `state/plugins/registry.json`
- docs/skills/skills.v0.1.md:84 — registry_path="state/plugins/registry.json",

### state/supervisor_capability_denies.json
- docs/supervisor-autonomy.v0.2.md:31 — Phase F optionally supports `state/supervisor_capability_denies.json`:

### supervisor/autonomy_budget_gate.py
- docs/adr/ADR-001-autonomy-budget-gate-redundancy-proof.md:8 — Legacy compatibility layer `supervisor/autonomy_budget_gate.py` required proof of runtime redundancy before removal.
- docs/roadmap/autonomy_budget_gate_redundancy_proof.md:4 — Scope: `supervisor/autonomy_budget_gate.py`
- docs/roadmap/autonomy_budget_gate_redundancy_proof.md:61 — `supervisor/autonomy_budget_gate.py` is verified unused in production/runtime codepaths and is safe to remove in a separate change set.
- docs/roadmap/codex_autonomy_progress.md:40 — - removed `supervisor/autonomy_budget_gate.py`

### supervisor/capability-revoke.v0.1.json
- governance/schema/supervisor/capability-revoke.v0.1.json:3 — "$id": "https://ai-os.local/schema/supervisor/capability-revoke.v0.1.json",

### supervisor/governance/user_policy.py
- docs/implementation-plan.v0.1.md:165 — - `supervisor/governance/user_policy.py`

### supervisor/phase_gate.py
- docs/phase-gate-runtime-enforcement-v0.1.md:25 — (optionally) one small helper module supervisor/phase_gate.py IF it is purely functional and does not add architecture

### supervisor/plugins/loader.py
- docs/implementation-plan.v0.1.md:92 — - `supervisor/plugins/loader.py`

### supervisor/plugins/validator.py
- docs/implementation-plan.v0.1.md:93 — - `supervisor/plugins/validator.py`

### supervisor/skills/framework.py
- docs/implementation-plan.v0.1.md:141 — - `supervisor/skills/framework.py`

### supervisor/skills/registry.py
- docs/implementation-plan.v0.1.md:142 — - `supervisor/skills/registry.py`

### supervisor/system_ops/executor.py
- docs/implementation-plan.v0.1.md:187 — - `supervisor/system_ops/executor.py`

### supervisor/system_ops/permit_gate.py
- docs/implementation-plan.v0.1.md:188 — - `supervisor/system_ops/permit_gate.py`

### supervisor/tests/test_autonomy_budget.py::test_invalid_state_file_fails_closed
- docs/roadmap/codex_autonomy_progress.md:47 — - `supervisor/tests/test_autonomy_budget.py::test_invalid_state_file_fails_closed`

### supervisor/tests/test_autonomy_budget_gate.py
- docs/roadmap/codex_autonomy_progress.md:41 — - removed `supervisor/tests/test_autonomy_budget_gate.py`

### supervisor/tests/test_cli.py:306
- docs/roadmap/codex_autonomy_progress.md:417 — - `supervisor/tests/test_cli.py:306`

## Grouped By Document

### docs/Specifications AI-OS/.obsidian/app.json
- none

### docs/Specifications AI-OS/.obsidian/appearance.json
- none

### docs/Specifications AI-OS/.obsidian/core-plugins.json
- none

### docs/Specifications AI-OS/.obsidian/graph.json
- none

### docs/Specifications AI-OS/.obsidian/themes/AbsoluteGruv/manifest.json
- none

### docs/Specifications AI-OS/.obsidian/themes/Apex/manifest.json
- none

### docs/Specifications AI-OS/.obsidian/themes/Minimal/manifest.json
- none

### docs/Specifications AI-OS/.obsidian/themes/Obsidian Nord/manifest.json
- none

### docs/Specifications AI-OS/.obsidian/themes/Terminal/manifest.json
- none

### docs/Specifications AI-OS/.obsidian/themes/WY Console/manifest.json
- none

### docs/Specifications AI-OS/.obsidian/themes/flexcyon/manifest.json
- docs/dark.png (docs/Specifications AI-OS/.obsidian/themes/flexcyon/manifest.json:6) — "screenshot": "./docs/dark.png",

### docs/Specifications AI-OS/.obsidian/workspace.json
- none

### docs/Specifications AI-OS/Agent Git Governance Spec v0.2.md
- none

### docs/Specifications AI-OS/Notes 02162026.md
- none

### docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md
- docs/Specifications AI-OS/.gitea/pull_request_template.md (docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:357) — 3. Add PR template in `.gitea/pull_request_template.md` (or repo equivalent)
- docs/Specifications AI-OS/All governance gates satisfied (policy v0.2, hash … (docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:349) — * **PASS:** `All governance gates satisfied (policy v0.2, hash …)`
- docs/Specifications AI-OS/artifacts/governance/pr-<num>-<headsha>.json (docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:246) — `artifacts/governance/pr-<num>-<headsha>.json`
- docs/Specifications AI-OS/environment.json (docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:320) — * The Supervisor should derive `owner/repo` dynamically from `environment.json` or git remote (aligns with your backlog item: remove hard-coded owner/repo).
- docs/Specifications AI-OS/git log --show-signature <base>..<head (docs/Specifications AI-OS/Supervisor PR Compliance Gate Spec v0.1.md:166) — * `git log --show-signature <base>..<head>`

### docs/adr/ADR-001-autonomy-budget-gate-redundancy-proof.md
- supervisor/autonomy_budget_gate.py (docs/adr/ADR-001-autonomy-budget-gate-redundancy-proof.md:8) — Legacy compatibility layer `supervisor/autonomy_budget_gate.py` required proof of runtime redundancy before removal.

### docs/adr/ADR-002-phase-acceptance-rule-enforcement.md
- none

### docs/adr/ADR-003-high-risk-token-gate-scope.md
- none

### docs/approval-token.md
- docs/.gitea/governance/supervisor-capabilities.v1.yaml (docs/approval-token.md:42) — - `.gitea/governance/supervisor-capabilities.v1.yaml`
- docs/body.payload (docs/approval-token.md:35) — - `body.payload` if present
- docs/home/infra/night/state/autonomy/approval-replay.sqlite3 (docs/approval-token.md:77) — - default `/home/infra/night/state/autonomy/approval-replay.sqlite3`
- docs/token = base64url(payload_json) + "." + base64url(hmac_sha256(APPROVAL_SECRET, base64url(payload_json)) (docs/approval-token.md:7) — `token = base64url(payload_json) + "." + base64url(hmac_sha256(APPROVAL_SECRET, base64url(payload_json)))`
- governance/supervisor-capabilities.v1.yaml (docs/approval-token.md:42) — - `.gitea/governance/supervisor-capabilities.v1.yaml`
- state/autonomy/approval-replay.sqlite3 (docs/approval-token.md:77) — - default `/home/infra/night/state/autonomy/approval-replay.sqlite3`

### docs/archive/conceptual/autonomous-evaluation-and-improvement-protocol-v0.1.md
- none

### docs/archive/conceptual/autonomous-planning-and-self-generated-task-protocol-v0.1.md
- none

### docs/archive/conceptual/daily-autonomous-execution-protocol-v0.1.md
- docs/archive/conceptual/agents/state/environment.json (docs/archive/conceptual/daily-autonomous-execution-protocol-v0.1.md:74) — - Configured in `agents/state/environment.json`
- state/environment.json (docs/archive/conceptual/daily-autonomous-execution-protocol-v0.1.md:74) — - Configured in `agents/state/environment.json`

### docs/archive/conceptual/long-term-memory-and-knowledge-consolidation-protocol-v0.1.md
- none

### docs/archive/conceptual/system-memory-and-learning-protocol-v0.1.md
- none

### docs/archive/conceptual/task-execution-engine-v0.1.md
- none

### docs/archive/governance_versions/Agent Git Governance Spec v0.1.md
- none

### docs/archive/governance_versions/governance-invariants.v0.1.md
- docs/archive/governance_versions/KillSwitchError.code (docs/archive/governance_versions/governance-invariants.v0.1.md:25) — - `KillSwitchError.code` compatibility contract is restored and covered by tests.
- docs/archive/governance_versions/commit_signing.accepted_types (docs/archive/governance_versions/governance-invariants.v0.1.md:16) — - `commit_signing.accepted_types` is enforced.
- docs/archive/governance_versions/commit_signing.mode (docs/archive/governance_versions/governance-invariants.v0.1.md:15) — - `commit_signing.mode` is enforced.
- docs/archive/governance_versions/gate-verdict.json (docs/archive/governance_versions/governance-invariants.v0.1.md:11) — - `gate-verdict.json` is machine-readable.
- docs/archive/governance_versions/governance-policy-sha.txt (docs/archive/governance_versions/governance-invariants.v0.1.md:35) — - Effective policy SHA anchor is recorded in [docs/governance-policy-sha.txt](./governance-policy-sha.txt).
- docs/archive/governance_versions/requirements-dev.txt (docs/archive/governance_versions/governance-invariants.v0.1.md:30) — - `requirements-dev.txt` is pinned.
- docs/archive/governance_versions/requirements.txt (docs/archive/governance_versions/governance-invariants.v0.1.md:29) — - `requirements.txt` is pinned.

### docs/autonomous-phase-transition-governance-v0.1.md
- none

### docs/channels/telegram.v0.1.md
- docs/channels/channel.telegram.message (docs/channels/telegram.v0.1.md:6) — `channel.telegram.message`.
- docs/channels/logs/control/channel-telegram.jsonl (docs/channels/telegram.v0.1.md:29) — - `logs/control/channel-telegram.jsonl`
- docs/channels/logs/control/channel-telegram.jsonl (docs/channels/telegram.v0.1.md:42) — - `AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH` (default: `logs/control/channel-telegram.jsonl`)
- docs/channels/logs/control/kernel-events.jsonl (docs/channels/telegram.v0.1.md:32) — - `logs/control/kernel-events.jsonl`
- docs/channels/logs/control/kernel-events.jsonl (docs/channels/telegram.v0.1.md:41) — - `AIOS_EVENT_AUDIT_LOG_PATH` (default: `logs/control/kernel-events.jsonl`)
- state/plugins/config.json (docs/channels/telegram.v0.1.md:40) — - `AIOS_CONFIG_PATH` (default: `state/plugins/config.json`)
- state/plugins/registry.json (docs/channels/telegram.v0.1.md:39) — - `AIOS_REGISTRY_PATH` (default: `state/plugins/registry.json`)

### docs/core_manifest.md
- none

### docs/deterministic-executor-dispatch-and-result-ingestion-v0.1.md
- none

### docs/deterministic-supervisor-loop-v0.1.md
- none

### docs/dispatch-api.v0.1.md
- docs/error.details[0 (docs/dispatch-api.v0.1.md:64) — Runner reason codes are preserved in `error.details[0]`.
- docs/kernel/plugins/runner.py (docs/dispatch-api.v0.1.md:9) — - Uses secure runner: `kernel/plugins/runner.py`
- state/plugins/config.json (docs/dispatch-api.v0.1.md:19) — `dispatch(plugin_id, method, payload, *, request_id=None, registry_path="state/plugins/registry.json", config_path="state/plugins/config.json", audit_log_path="logs/control/plugin-runtime.jsonl", runner_state_dir_base="state/plugins/runtime", timeout_override_seconds=None) -> dict`
- state/plugins/registry.json (docs/dispatch-api.v0.1.md:19) — `dispatch(plugin_id, method, payload, *, request_id=None, registry_path="state/plugins/registry.json", config_path="state/plugins/config.json", audit_log_path="logs/control/plugin-runtime.jsonl", runner_state_dir_base="state/plugins/runtime", timeout_override_seconds=None) -> dict`

### docs/environment.md
- none

### docs/evaluation-and-commit-protocol-v0.1.md
- state/environment.json (docs/evaluation-and-commit-protocol-v0.1.md:114) — agents/state/environment.json

### docs/event-bus.v0.1.md
- docs/kernel.dispatch.dispatch( (docs/event-bus.v0.1.md:4) — Provide an internal-only event fan-out API that routes kernel events to enabled plugins through `kernel.dispatch.dispatch()`.
- docs/logs/control/kernel-events.jsonl (docs/event-bus.v0.1.md:52) — - Audit file: `logs/control/kernel-events.jsonl`.
- docs/plugins.{plugin_id}.enabled == true (docs/event-bus.v0.1.md:47) — - `plugins.{plugin_id}.enabled == true`
- docs/subscriptions: ["event.a", "event.b" (docs/event-bus.v0.1.md:39) — - `subscriptions: ["event.a", "event.b"]`
- state/plugins/config.json (docs/event-bus.v0.1.md:19) — config_path="state/plugins/config.json",
- state/plugins/registry.json (docs/event-bus.v0.1.md:18) — registry_path="state/plugins/registry.json",

### docs/gitea-ci-setup.md
- docs/.gitea/governance/path-allowlist.v1.yaml (docs/gitea-ci-setup.md:45) — - `.gitea/governance/path-allowlist.v1.yaml`
- docs/.gitea/workflows/pr-gate.yml (docs/gitea-ci-setup.md:7) — - File: `.gitea/workflows/pr-gate.yml`
- docs/gate-verdict.json (docs/gitea-ci-setup.md:53) — - `gate-verdict.json`
- docs/gate-verdict.json (docs/gitea-ci-setup.md:77) — Workflow always emits `gate-verdict.json` and prints it in logs via the `Emit gate verdict` step.
- governance/path-allowlist.v1.yaml (docs/gitea-ci-setup.md:45) — - `.gitea/governance/path-allowlist.v1.yaml`

### docs/governance-commit-policy-regex-fix-v0.1.md
- docs/executor/dispatch.py (docs/governance-commit-policy-regex-fix-v0.1.md:83) — - `executor/dispatch.py`
- docs/python3 -m py_compile supervisor/governance_enforcement.py (docs/governance-commit-policy-regex-fix-v0.1.md:78) — 1) `python3 -m py_compile supervisor/governance_enforcement.py`

### docs/governance-invariants.v0.2.md
- docs/335 passed, 2 warnings in 5.18s (docs/governance-invariants.v0.2.md:4) — - Exact pytest summary: `335 passed, 2 warnings in 5.18s`

### docs/governance-policy-sha.txt
- none

### docs/governance.md
- docs/agents/state/environment.json (docs/governance.md:78) — `agents/state/environment.json`. Refer to those files for details.)
- state/environment.json (docs/governance.md:78) — `agents/state/environment.json`. Refer to those files for details.)

### docs/hardening/container-hardening.v0.1.md
- docs/hardening/app/logs/control/channel-telegram.jsonl (docs/hardening/container-hardening.v0.1.md:68) — - `AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH` (default `/app/logs/control/channel-telegram.jsonl`)
- docs/hardening/app/logs/control/kernel-events.jsonl (docs/hardening/container-hardening.v0.1.md:67) — - `AIOS_EVENT_AUDIT_LOG_PATH` (default `/app/logs/control/kernel-events.jsonl`)
- docs/hardening/app/state/plugins/config.json (docs/hardening/container-hardening.v0.1.md:66) — - `AIOS_CONFIG_PATH` (default `/app/state/plugins/config.json`)
- docs/hardening/app/state/plugins/registry.json (docs/hardening/container-hardening.v0.1.md:65) — - `AIOS_REGISTRY_PATH` (default `/app/state/plugins/registry.json`)
- docs/hardening/docker/Dockerfile.webhook (docs/hardening/container-hardening.v0.1.md:27) — - `docker/Dockerfile.webhook`
- docs/hardening/docker/docker-compose.yml (docs/hardening/container-hardening.v0.1.md:28) — - `docker/docker-compose.yml`
- state/plugins/config.json (docs/hardening/container-hardening.v0.1.md:66) — - `AIOS_CONFIG_PATH` (default `/app/state/plugins/config.json`)
- state/plugins/registry.json (docs/hardening/container-hardening.v0.1.md:65) — - `AIOS_REGISTRY_PATH` (default `/app/state/plugins/registry.json`)

### docs/hardening/nginx-telegram-reverse-proxy.v0.1.md
- docs/hardening/TLSv1.2 (docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:15) — - TLS downgrade: HTTP traffic is redirected to HTTPS and TLS is restricted to `TLSv1.2`/`TLSv1.3`.
- docs/hardening/TLSv1.3 (docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:15) — - TLS downgrade: HTTP traffic is redirected to HTTPS and TLS is restricted to `TLSv1.2`/`TLSv1.3`.
- docs/hardening/docker/nginx/aios-telegram.conf (docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:22) — - `docker/nginx/aios-telegram.conf`
- docs/hardening/docker/nginx/nginx.conf (docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:21) — - `docker/nginx/nginx.conf`
- docs/hardening/etc/letsencrypt/live/your-domain.com/fullchain.pem (docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:71) — - `/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- docs/hardening/etc/letsencrypt/live/your-domain.com/privkey.pem (docs/hardening/nginx-telegram-reverse-proxy.v0.1.md:72) — - `/etc/letsencrypt/live/your-domain.com/privkey.pem`

### docs/implementation-plan.v0.1.md
- docs/.gitea/governance/path-allowlist.v1.yaml (docs/implementation-plan.v0.1.md:79) — - [ ] Evaluator command runs `scripts/pr_gate_path_allowlist.py` with policy path `.gitea/governance/path-allowlist.v1.yaml`.
- docs/.gitea/workflows/pr-gate.yml (docs/implementation-plan.v0.1.md:56) — - `.gitea/workflows/pr-gate.yml`
- docs/.gitea/workflows/pr-gate.yml (docs/implementation-plan.v0.1.md:77) — - [ ] `.gitea/workflows/pr-gate.yml` exists and triggers on PR `opened|synchronize|reopened`.
- docs/bash scripts/test-pr-gate-m1.sh (docs/implementation-plan.v0.1.md:83) — - `bash scripts/test-pr-gate-m1.sh`
- docs/channel-boundaries.v0.1.md (docs/implementation-plan.v0.1.md:120) — - `docs/channel-boundaries.v0.1.md`
- docs/gate-verdict.json (docs/implementation-plan.v0.1.md:68) — - `gate-verdict.json` generated in CI run workspace.
- docs/gate-verdict.json (docs/implementation-plan.v0.1.md:80) — - [ ] Workflow emits `gate-verdict.json` and fails closed on missing token/API base/evaluator error.
- docs/plugins-boundary.v0.1.md (docs/implementation-plan.v0.1.md:94) — - `docs/plugins-boundary.v0.1.md`
- docs/skill-boundaries.v0.1.md (docs/implementation-plan.v0.1.md:143) — - `docs/skill-boundaries.v0.1.md`
- docs/system-ops-executor.v0.1.md (docs/implementation-plan.v0.1.md:189) — - `docs/system-ops-executor.v0.1.md`
- docs/tests/test_gateway_boundary.py (docs/implementation-plan.v0.1.md:121) — - `tests/test_gateway_boundary.py`
- docs/tests/test_plugin_boundary_validator.py (docs/implementation-plan.v0.1.md:96) — - `tests/test_plugin_boundary_validator.py`
- docs/tests/test_plugin_loader.py (docs/implementation-plan.v0.1.md:95) — - `tests/test_plugin_loader.py`
- docs/tests/test_pr_gate_gitea_workflow.py (docs/implementation-plan.v0.1.md:58) — - `tests/test_pr_gate_gitea_workflow.py` (integration/contract test)
- docs/tests/test_skill_framework.py (docs/implementation-plan.v0.1.md:144) — - `tests/test_skill_framework.py`
- docs/tests/test_system_ops_executor.py (docs/implementation-plan.v0.1.md:190) — - `tests/test_system_ops_executor.py`
- docs/tests/test_user_policy_validation.py (docs/implementation-plan.v0.1.md:167) — - `tests/test_user_policy_validation.py`
- docs/user-governance-ui.v0.1.md (docs/implementation-plan.v0.1.md:166) — - `docs/user-governance-ui.v0.1.md`
- governance/path-allowlist.v1.yaml (docs/implementation-plan.v0.1.md:79) — - [ ] Evaluator command runs `scripts/pr_gate_path_allowlist.py` with policy path `.gitea/governance/path-allowlist.v1.yaml`.
- supervisor/governance/user_policy.py (docs/implementation-plan.v0.1.md:165) — - `supervisor/governance/user_policy.py`
- supervisor/plugins/loader.py (docs/implementation-plan.v0.1.md:92) — - `supervisor/plugins/loader.py`
- supervisor/plugins/validator.py (docs/implementation-plan.v0.1.md:93) — - `supervisor/plugins/validator.py`
- supervisor/skills/framework.py (docs/implementation-plan.v0.1.md:141) — - `supervisor/skills/framework.py`
- supervisor/skills/registry.py (docs/implementation-plan.v0.1.md:142) — - `supervisor/skills/registry.py`
- supervisor/system_ops/executor.py (docs/implementation-plan.v0.1.md:187) — - `supervisor/system_ops/executor.py`
- supervisor/system_ops/permit_gate.py (docs/implementation-plan.v0.1.md:188) — - `supervisor/system_ops/permit_gate.py`

### docs/ipc-runner.v0.1.md
- docs/runtime.timeout_seconds (docs/ipc-runner.v0.1.md:37) — - `runtime.timeout_seconds` must be present and > 0.

### docs/multi-cycle-deterministic-scheduler-v0.1.md
- none

### docs/night-executor-v0.1.md
- docs/evaluations.jsonl (docs/night-executor-v0.1.md:71) — `LEDGER_DIR` (or `--ledger-dir`), so `runs.jsonl` and `evaluations.jsonl`
- docs/home/infra/night/state/autonomy/budget-log.jsonl (docs/night-executor-v0.1.md:183) — - `/home/infra/night/state/autonomy/budget-log.jsonl`
- docs/home/infra/night/state/autonomy/budget.json (docs/night-executor-v0.1.md:182) — - `/home/infra/night/state/autonomy/budget.json`
- docs/home/infra/night/state/autonomy/inbox/tasks/<task_id>.json (docs/night-executor-v0.1.md:160) — - Inbox path: `/home/infra/night/state/autonomy/inbox/tasks/<task_id>.json`
- docs/home/infra/night/state/autonomy/intake-log.jsonl (docs/night-executor-v0.1.md:161) — - Intake log: `/home/infra/night/state/autonomy/intake-log.jsonl`
- docs/ledger/runs.jsonl (docs/night-executor-v0.1.md:50) — into `ledger/runs.jsonl` (idempotent by `run_id`).
- docs/night-autonomy-promote-v0.1 (docs/night-executor-v0.1.md:140) — Queue mode `night-autonomy-promote-v0.1` runs:
- docs/runs.jsonl (docs/night-executor-v0.1.md:71) — `LEDGER_DIR` (or `--ledger-dir`), so `runs.jsonl` and `evaluations.jsonl`
- docs/scripts/night-autonomy-dryrun.sh (docs/night-executor-v0.1.md:134) — `./scripts/night-autonomy-dryrun.sh`
- docs/scripts/test-all.sh (docs/night-executor-v0.1.md:30) — - Runs `./scripts/test-all.sh`.
- docs/supervisor.autonomy_promotion_gate (docs/night-executor-v0.1.md:144) — 3. Deterministic draft PR promotion via `supervisor.autonomy_promotion_gate`.
- docs/supervisor.autonomy_promotion_gate (docs/night-executor-v0.1.md:216) — - `supervisor.autonomy_promotion_gate` (`promotion`)
- docs/supervisor.autonomy_review_intake_gate (docs/night-executor-v0.1.md:217) — - `supervisor.autonomy_review_intake_gate` (`intake`)
- docs/supervisor.autonomy_task_materializer (docs/night-executor-v0.1.md:157) — `supervisor.autonomy_task_materializer` converts intake-approved autonomy proposal PRs
- docs/supervisor.autonomy_task_materializer (docs/night-executor-v0.1.md:218) — - `supervisor.autonomy_task_materializer` (`materialize`)
- docs/supervisor.budgets.autonomy (docs/night-executor-v0.1.md:178) — Budget gate module: `supervisor.budgets.autonomy` (canonical runtime path)
- docs/supervisor.environment_validation (docs/night-executor-v0.1.md:33) — `supervisor.environment_validation`.
- docs/supervisor.ledger.ingest_evaluation_record_linked (docs/night-executor-v0.1.md:55) — `supervisor.ledger.ingest_evaluation_record_linked`.
- docs/supervisor.night_executor (docs/night-executor-v0.1.md:219) — - `supervisor.night_executor` attempts (`exec_attempt`) and commits (`commit`)
- docs/supervisor.night_task_runner.execute_night_task (docs/night-executor-v0.1.md:59) — - Uses `supervisor.night_task_runner.execute_night_task` adapter, which
- docs/supervisor.results.ingest_run_record (docs/night-executor-v0.1.md:49) — - Ingests run records via `supervisor.results.ingest_run_record`
- docs/supervisor.supervisor.dispatch_task_with_supervisor_permit (docs/night-executor-v0.1.md:60) — calls `supervisor.supervisor.dispatch_task_with_supervisor_permit`
- state/autonomy/budget-log.jsonl (docs/night-executor-v0.1.md:183) — - `/home/infra/night/state/autonomy/budget-log.jsonl`
- state/autonomy/budget.json (docs/night-executor-v0.1.md:182) — - `/home/infra/night/state/autonomy/budget.json`
- state/autonomy/intake-log.jsonl (docs/night-executor-v0.1.md:161) — - Intake log: `/home/infra/night/state/autonomy/intake-log.jsonl`
- state/night-reports/night-report.<UTC>.json (docs/night-executor-v0.1.md:68) — `state/night-reports/night-report.<UTC>.json`

### docs/night-mode.v0.1.md
- docs/NIGHT_BRANCH=dev ./scripts/night-bootstrap.sh (docs/night-mode.v0.1.md:10) — Example: `NIGHT_BRANCH=dev ./scripts/night-bootstrap.sh`
- docs/script/test-all.sh (docs/night-mode.v0.1.md:11) — For compatibility across repositories, harness discovery supports `./scripts/test-all.sh` first and `./script/test-all.sh` as fallback.
- docs/scripts/test-all.sh (docs/night-mode.v0.1.md:8) — The script ensures the Night workspace is a clean clone/reset state and that `./scripts/test-all.sh` passes in that workspace.
- docs/scripts/test-all.sh (docs/night-mode.v0.1.md:11) — For compatibility across repositories, harness discovery supports `./scripts/test-all.sh` first and `./script/test-all.sh` as fallback.

### docs/phase-acceptance-rule.v0.1.md
- docs/v0.1 (docs/phase-acceptance-rule.v0.1.md:19) — - `version` (must be `v0.1`)

### docs/phase-gate-governance-protocol-v0.1.md
- state/active_phase.json (docs/phase-gate-governance-protocol-v0.1.md:152) — agents/state/active_phase.json

### docs/phase-gate-multi-cycle-scheduler-v0.1.md
- none

### docs/phase-gate-runtime-enforcement-v0.1.md
- supervisor/phase_gate.py (docs/phase-gate-runtime-enforcement-v0.1.md:25) — (optionally) one small helper module supervisor/phase_gate.py IF it is purely functional and does not add architecture

### docs/plugins-ops.md
- docs/config.json (docs/plugins-ops.md:11) — `config.json` is operator-owned enablement state.
- docs/config.json (docs/plugins-ops.md:15) — - `config.json` canonical shape:
- docs/config.json (docs/plugins-ops.md:19) — Canonical `config.json`:
- docs/logs/control/plugin-events.jsonl (docs/plugins-ops.md:54) — - Append-only JSONL: `logs/control/plugin-events.jsonl`
- docs/python scripts/aios_plugins.py disable <plugin_id (docs/plugins-ops.md:45) — - `python scripts/aios_plugins.py disable <plugin_id>`
- docs/python scripts/aios_plugins.py enable <plugin_id (docs/plugins-ops.md:44) — - `python scripts/aios_plugins.py enable <plugin_id>`
- docs/python scripts/aios_plugins.py list (docs/plugins-ops.md:43) — - `python scripts/aios_plugins.py list`
- docs/python scripts/aios_plugins.py set-unsafe-external true|false (docs/plugins-ops.md:46) — - `python scripts/aios_plugins.py set-unsafe-external true|false`
- docs/registry.json (docs/plugins-ops.md:10) — `registry.json` is discovery output. It is read-only for operators.
- docs/registry.json (docs/plugins-ops.md:14) — - `registry.json` contains discovered plugin metadata (`plugin_id`, `version`, `trust_tier`, `path`, `fingerprint`, `api_version`).
- docs/registry.json (docs/plugins-ops.md:41) — 1. Refresh discovery into `registry.json`.
- state/plugins/config.json (docs/plugins-ops.md:8) — - Operator config: `state/plugins/config.json`
- state/plugins/registry.json (docs/plugins-ops.md:7) — - Registry: `state/plugins/registry.json`

### docs/plugins.md
- docs/*/plugin.yaml (docs/plugins.md:12) — Discovery target is `*/plugin.yaml`.
- docs/execution.out_of_process: true (docs/plugins.md:52) — Plugins are out-of-process (`execution.out_of_process: true`) and may not modify kernel or runtime internals.
- docs/plugin.yaml (docs/plugins.md:38) — Official plugins must have `signing.registry_signed: true` in `plugin.yaml`.
- docs/signing.registry_signed: true (docs/plugins.md:38) — Official plugins must have `signing.registry_signed: true` in `plugin.yaml`.
- docs/{"id":"<uuid>","ok":true|false,...} (docs/plugins.md:71) — - `{"id":"<uuid>","ok":true|false,...}`
- docs/{"type":"request","id":"<uuid>","capability":"notify:escalation","payload":{...}} (docs/plugins.md:69) — - `{"type":"request","id":"<uuid>","capability":"notify:escalation","payload":{...}}`
- state/plugins/registry.json (docs/plugins.md:23) — - `state/plugins/registry.json`

### docs/pr-gate-path-allowlist.md
- docs/.gitea/governance/path-allowlist.v1.yaml (docs/pr-gate-path-allowlist.md:6) — - Policy file: `.gitea/governance/path-allowlist.v1.yaml`
- docs/.gitea/governance/path-allowlist.v1.yaml (docs/pr-gate-path-allowlist.md:32) — 3. Loads and evaluates `.gitea/governance/path-allowlist.v1.yaml`
- docs/.github/workflows/pr-gate-path-allowlist.yml (docs/pr-gate-path-allowlist.md:21) — Workflow file: `.github/workflows/pr-gate-path-allowlist.yml`
- docs/gate-verdict.json (docs/pr-gate-path-allowlist.md:33) — 4. Writes `gate-verdict.json`
- docs/gate-verdict.json (docs/pr-gate-path-allowlist.md:34) — 5. Uploads `gate-verdict.json` as workflow artifact
- docs/gate-verdict.json (docs/pr-gate-path-allowlist.md:38) — The evaluator writes `gate-verdict.json`:
- governance/path-allowlist.v1.yaml (docs/pr-gate-path-allowlist.md:6) — - Policy file: `.gitea/governance/path-allowlist.v1.yaml`
- governance/path-allowlist.v1.yaml (docs/pr-gate-path-allowlist.md:32) — 3. Loads and evaluates `.gitea/governance/path-allowlist.v1.yaml`

### docs/pre-execution-environment-validation-v0.1.md
- state/environment.json (docs/pre-execution-environment-validation-v0.1.md:115) — agents/state/environment.json

### docs/recursive-self-improvement-governance-v0.1.md
- none

### docs/roadmap/autonomy_budget_gate_redundancy_proof.md
- docs/roadmap/supervisor.autonomy_budget (docs/roadmap/autonomy_budget_gate_redundancy_proof.md:24) — - `supervisor/night_executor.py` budget checks now route through `supervisor.autonomy_budget`.
- docs/roadmap/supervisor.autonomy_budget_gate (docs/roadmap/autonomy_budget_gate_redundancy_proof.md:25) — - No production import of `supervisor.autonomy_budget_gate` remains.
- supervisor/autonomy_budget_gate.py (docs/roadmap/autonomy_budget_gate_redundancy_proof.md:4) — Scope: `supervisor/autonomy_budget_gate.py`
- supervisor/autonomy_budget_gate.py (docs/roadmap/autonomy_budget_gate_redundancy_proof.md:61) — `supervisor/autonomy_budget_gate.py` is verified unused in production/runtime codepaths and is safe to remove in a separate change set.

### docs/roadmap/codex_autonomy_progress.md
- docs/roadmap/422 passed, 14 skipped in 23.67s (docs/roadmap/codex_autonomy_progress.md:421) — - `422 passed, 14 skipped in 23.67s` (`pytest -q`)
- docs/roadmap/428 passed, 14 skipped in 27.36s (docs/roadmap/codex_autonomy_progress.md:465) — - full suite: `428 passed, 14 skipped in 27.36s` (`pytest -q`)
- docs/roadmap/431 passed, 14 skipped in 27.04s (docs/roadmap/codex_autonomy_progress.md:501) — - full suite: `431 passed, 14 skipped in 27.04s` (`pytest -q`)
- docs/roadmap/autonomy_orchestrator/night_mode.py (docs/roadmap/codex_autonomy_progress.md:170) — - `autonomy_orchestrator/night_mode.py`
- docs/roadmap/autonomy_orchestrator/night_mode.py (docs/roadmap/codex_autonomy_progress.md:189) — - night mode pre-execution flow (`autonomy_orchestrator/night_mode.py`)
- docs/roadmap/home/infra/AI-OS/governance_policy.yaml (docs/roadmap/codex_autonomy_progress.md:94) — - Phase-K budget tests require `/home/infra/AI-OS/governance_policy.yaml`
- docs/roadmap/logs/control/approval_token_audit.jsonl (docs/roadmap/codex_autonomy_progress.md:129) — - SHA256 token hash logging added to audit stream (`logs/control/approval_token_audit.jsonl`)
- docs/roadmap/logs/control/interrupts/<date>/interrupt__<checkpoint>.json (docs/roadmap/codex_autonomy_progress.md:153) — - `logs/control/interrupts/<date>/interrupt__<checkpoint>.json`
- docs/roadmap/orchestrator/commit_flow.py (docs/roadmap/codex_autonomy_progress.md:20) — - `orchestrator/commit_flow.py` (passes explicit changed file list)
- docs/roadmap/orchestrator/git.py (docs/roadmap/codex_autonomy_progress.md:14) — - `orchestrator/git.py`
- docs/roadmap/orchestrator/git.py (docs/roadmap/codex_autonomy_progress.md:19) — - `orchestrator/git.py` (`commit()` now stages explicit files)
- docs/roadmap/orchestrator/git.py (docs/roadmap/codex_autonomy_progress.md:171) — - `orchestrator/git.py`
- docs/roadmap/requests/capabilities/night_mode/<epoch>__issue_<id>__<task_hash>.json (docs/roadmap/codex_autonomy_progress.md:440) — - `requests/capabilities/night_mode/<epoch>__issue_<id>__<task_hash>.json`
- docs/roadmap/supervisor.autonomy_budget (docs/roadmap/codex_autonomy_progress.md:33) — - `supervisor/night_executor.py` now uses `supervisor.autonomy_budget` via a compatibility adapter (`check_and_consume`)
- docs/roadmap/supervisor.autonomy_budget (docs/roadmap/codex_autonomy_progress.md:61) — - no production imports remain for `supervisor.autonomy_budget` or `supervisor.autonomy_budget_gate`
- docs/roadmap/supervisor.autonomy_budget_gate (docs/roadmap/codex_autonomy_progress.md:34) — - removed direct runtime dependency on `supervisor.autonomy_budget_gate` internals
- docs/roadmap/supervisor.autonomy_budget_gate (docs/roadmap/codex_autonomy_progress.md:61) — - no production imports remain for `supervisor.autonomy_budget` or `supervisor.autonomy_budget_gate`
- docs/roadmap/supervisor.budgets.autonomy (docs/roadmap/codex_autonomy_progress.md:44) — - updated runtime and gate imports to `supervisor.budgets.autonomy`
- docs/roadmap/sys.executable (docs/roadmap/codex_autonomy_progress.md:103) — - plugin-loader tests now use `sys.executable` (environment-agnostic process launch)
- docs/roadmap/tests/test_aiosctl_scheduler_tick.py (docs/roadmap/codex_autonomy_progress.md:156) — - `tests/test_aiosctl_scheduler_tick.py` (scheduler tick interrupt halt)
- docs/roadmap/tests/test_aiosctl_scheduler_tick.py (docs/roadmap/codex_autonomy_progress.md:158) — - targeted run: `25 passed` (`tests/test_night_mode.py`, `tests/test_aiosctl_scheduler_tick.py`)
- docs/roadmap/tests/test_aiosctl_scheduler_tick.py::test_scheduler_tick_denies_when_budget_state_is_tampered (docs/roadmap/codex_autonomy_progress.md:197) — - `tests/test_aiosctl_scheduler_tick.py::test_scheduler_tick_denies_when_budget_state_is_tampered`
- docs/roadmap/tests/test_git_remote.py (docs/roadmap/codex_autonomy_progress.md:51) — - `tests/test_git_remote.py`
- docs/roadmap/tests/test_mutation_boundary.py (docs/roadmap/codex_autonomy_progress.md:22) — - `tests/test_mutation_boundary.py`
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:86) — - No governance bypass possible: covered by existing fail-closed tests in `tests/test_night_mode.py` (`DENY_*` paths).
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:89) — - Targeted Phase 2 suite: `29 passed` (`tests/test_night_mode.py`, scheduler, budget suites).
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:90) — - `tests/test_night_mode.py`: `20 passed`.
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:155) — - `tests/test_night_mode.py` (phase-boundary + pre-budget interrupt halt)
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:158) — - targeted run: `25 passed` (`tests/test_night_mode.py`, `tests/test_aiosctl_scheduler_tick.py`)
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:453) — - `tests/test_night_mode.py`
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:464) — - targeted suite: `29 passed` (`tests/test_night_mode.py`)
- docs/roadmap/tests/test_night_mode.py (docs/roadmap/codex_autonomy_progress.md:500) — - `tests/test_night_mode.py`
- docs/roadmap/tests/test_night_mode.py::test_identical_output_for_identical_state (docs/roadmap/codex_autonomy_progress.md:79) — - `tests/test_night_mode.py::test_identical_output_for_identical_state`
- docs/roadmap/tests/test_night_mode.py::test_night_mode_denies_on_budget_state_tamper (docs/roadmap/codex_autonomy_progress.md:196) — - `tests/test_night_mode.py::test_night_mode_denies_on_budget_state_tamper`
- docs/roadmap/tests/test_night_mode.py::test_summary_has_only_controlled_time_field (docs/roadmap/codex_autonomy_progress.md:80) — - `tests/test_night_mode.py::test_summary_has_only_controlled_time_field`
- docs/roadmap/tests/test_night_mode.py::test_three_consecutive_night_runs_succeed (docs/roadmap/codex_autonomy_progress.md:78) — - `tests/test_night_mode.py::test_three_consecutive_night_runs_succeed`
- docs/roadmap/tests/test_night_mode_local_intake.py (docs/roadmap/codex_autonomy_progress.md:499) — - `tests/test_night_mode_local_intake.py`
- docs/roadmap/tests/test_night_mode_local_intake.py::test_local_email_issue_missing_capability_emits_request_and_denies (docs/roadmap/codex_autonomy_progress.md:493) — - `tests/test_night_mode_local_intake.py::test_local_email_issue_missing_capability_emits_request_and_denies`
- docs/roadmap/tests/test_night_mode_local_intake.py::test_local_hello_world_issue_creates_file_and_halts (docs/roadmap/codex_autonomy_progress.md:491) — - `tests/test_night_mode_local_intake.py::test_local_hello_world_issue_creates_file_and_halts`
- docs/roadmap/tests/test_night_mode_local_intake.py::test_local_queue_recheck_processes_in_order_and_halts_when_empty (docs/roadmap/codex_autonomy_progress.md:495) — - `tests/test_night_mode_local_intake.py::test_local_queue_recheck_processes_in_order_and_halts_when_empty`
- docs/roadmap/tests/test_orchestrator_git_remote.py (docs/roadmap/codex_autonomy_progress.md:52) — - `tests/test_orchestrator_git_remote.py`
- docs/roadmap/tests/test_self_improvement_boundary_scan.py (docs/roadmap/codex_autonomy_progress.md:270) — - `tests/test_self_improvement_boundary_scan.py`
- docs/roadmap/tests/test_self_improvement_boundary_scan.py (docs/roadmap/codex_autonomy_progress.md:290) — - `tests/test_self_improvement_boundary_scan.py`
- docs/roadmap/tests/test_self_improvement_boundary_scan.py (docs/roadmap/codex_autonomy_progress.md:358) — - targeted suites: `16 passed` (`tests/test_self_improvement_pipeline.py`, `tests/test_self_improvement_boundary_scan.py`)
- docs/roadmap/tests/test_self_improvement_pipeline.py (docs/roadmap/codex_autonomy_progress.md:242) — - `tests/test_self_improvement_pipeline.py`
- docs/roadmap/tests/test_self_improvement_pipeline.py (docs/roadmap/codex_autonomy_progress.md:289) — - `tests/test_self_improvement_pipeline.py`
- docs/roadmap/tests/test_self_improvement_pipeline.py (docs/roadmap/codex_autonomy_progress.md:351) — - `tests/test_self_improvement_pipeline.py`
- docs/roadmap/tests/test_self_improvement_pipeline.py (docs/roadmap/codex_autonomy_progress.md:358) — - targeted suites: `16 passed` (`tests/test_self_improvement_pipeline.py`, `tests/test_self_improvement_boundary_scan.py`)
- docs/roadmap/tests/test_self_improvement_pipeline.py (docs/roadmap/codex_autonomy_progress.md:390) — - extended tests in `tests/test_self_improvement_pipeline.py`:
- docs/roadmap/tests/test_self_improvement_pipeline.py:153 (docs/roadmap/codex_autonomy_progress.md:408) — - `tests/test_self_improvement_pipeline.py:153`
- docs/roadmap/tests/test_self_improvement_pipeline.py:517 (docs/roadmap/codex_autonomy_progress.md:411) — - `tests/test_self_improvement_pipeline.py:517`
- docs/roadmap/tests/test_self_improvement_pipeline.py:631 (docs/roadmap/codex_autonomy_progress.md:414) — - `tests/test_self_improvement_pipeline.py:631`
- docs/roadmap/tests/test_state_json_determinism.py (docs/roadmap/codex_autonomy_progress.md:24) — - `tests/test_state_json_determinism.py`
- docs/roadmap/tests/test_supervisor_boundary_imports.py (docs/roadmap/codex_autonomy_progress.md:173) — - `tests/test_supervisor_boundary_imports.py`
- docs/roadmap/tests/test_utc_enforcement.py (docs/roadmap/codex_autonomy_progress.md:49) — - `tests/test_utc_enforcement.py`
- state/capability_requests/<epoch>__<issue_id>__<capability>.json (docs/roadmap/codex_autonomy_progress.md:486) — - `state/capability_requests/<epoch>__<issue_id>__<capability>.json`
- state/issues/open/*.json (docs/roadmap/codex_autonomy_progress.md:475) — - `state/issues/open/*.json`
- state/issues/open/*.md (docs/roadmap/codex_autonomy_progress.md:476) — - `state/issues/open/*.md`
- supervisor/autonomy_budget_gate.py (docs/roadmap/codex_autonomy_progress.md:40) — - removed `supervisor/autonomy_budget_gate.py`
- supervisor/tests/test_autonomy_budget.py::test_invalid_state_file_fails_closed (docs/roadmap/codex_autonomy_progress.md:47) — - `supervisor/tests/test_autonomy_budget.py::test_invalid_state_file_fails_closed`
- supervisor/tests/test_autonomy_budget_gate.py (docs/roadmap/codex_autonomy_progress.md:41) — - removed `supervisor/tests/test_autonomy_budget_gate.py`
- supervisor/tests/test_cli.py:306 (docs/roadmap/codex_autonomy_progress.md:417) — - `supervisor/tests/test_cli.py:306`

### docs/roadmap/codex_autonomy_roadmap.md
- docs/roadmap/*.json (docs/roadmap/codex_autonomy_roadmap.md:458) — - [x] Step 1: Add deterministic local intake source from `state/issues/open/*.md` and `*.json`.
- docs/roadmap/autonomy_orchestrator/night_mode.py (docs/roadmap/codex_autonomy_roadmap.md:484) — - [x] Confirmed runtime gate is HIGH-only in `autonomy_orchestrator/night_mode.py` (`is_self_improvement and risk_tier == "HIGH"`).
- docs/roadmap/determinism_evidence.json (docs/roadmap/codex_autonomy_roadmap.md:242) — - [x] Define `determinism_evidence.json` schema.
- docs/roadmap/helloworld.txt (docs/roadmap/codex_autonomy_roadmap.md:466) — - [x] Step 9: Add positive test: hello-world local issue creates `helloworld.txt` via governed flow.
- docs/roadmap/sys.executable (docs/roadmap/codex_autonomy_roadmap.md:83) — - [x] Remediation 1: Normalize plugin-loader tests to environment Python (`sys.executable`)
- state/issues/open/*.md (docs/roadmap/codex_autonomy_roadmap.md:458) — - [x] Step 1: Add deterministic local intake source from `state/issues/open/*.md` and `*.json`.
- state/issues/open/901-high-star.json (docs/roadmap/codex_autonomy_roadmap.md:483) — - [x] Diagnosed `DENY_TOKEN_MISSING` on user machine as HIGH-risk input issue (`state/issues/open/901-high-star.json`), not branch mismatch.

### docs/safety-kernel-and-hard-kill-switch-architecture-v0.1.md
- none

### docs/self-generated-governed-task-creation-v0.1.md
- none

### docs/self-generated-task-planning-protocol-v0.1.md
- none

### docs/skills/skills.v0.1.md
- docs/skills/channels.<id>.quotas.per_user_per_hour (docs/skills/skills.v0.1.md:98) — 5. Quota enforcement (`channels.<id>.quotas.per_user_per_hour`)
- docs/skills/kernel.dispatch (docs/skills/skills.v0.1.md:4) — The Skills Mediation Layer sits above `kernel.dispatch` and enforces deny-by-default authorization for external channels before any plugin method invocation.
- docs/skills/python -m unittest -v tests.test_skills_policy (docs/skills/skills.v0.1.md:128) — - `python -m unittest -v tests.test_skills_policy`
- docs/skills/rate_limit.cooldown_seconds (docs/skills/skills.v0.1.md:97) — 4. Cooldown enforcement (`rate_limit.cooldown_seconds`)
- docs/skills/result.ok == true (docs/skills/skills.v0.1.md:105) — - Cooldown state is updated only after successful dispatch (`result.ok == true`).
- state/plugins/config.json (docs/skills/skills.v0.1.md:85) — config_path="state/plugins/config.json",
- state/plugins/registry.json (docs/skills/skills.v0.1.md:84) — registry_path="state/plugins/registry.json",

### docs/specs/controlled-runtime-enforcement-plan-v0.1.md
- docs/specs/event_type=permit.issued (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:31) — - issuance audit event proposal (`event_type=permit.issued`)
- docs/specs/secure_layer.enforce.ambiguous_mapping (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:81) — - `secure_layer.enforce.ambiguous_mapping`
- docs/specs/secure_layer.enforce.chain_mismatch (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:78) — - `secure_layer.enforce.chain_mismatch`
- docs/specs/secure_layer.enforce.invalid_permit (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:77) — - `secure_layer.enforce.invalid_permit`
- docs/specs/secure_layer.enforce.policy_mismatch (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:79) — - `secure_layer.enforce.policy_mismatch`
- docs/specs/secure_layer.enforce.replay_mismatch (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:83) — - `secure_layer.enforce.replay_mismatch`
- docs/specs/secure_layer.enforce.review_missing (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:80) — - `secure_layer.enforce.review_missing`
- docs/specs/secure_layer.enforce.unbound_request (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:82) — - `secure_layer.enforce.unbound_request`
- governance/reviews/<review_id>.review.json (docs/specs/controlled-runtime-enforcement-plan-v0.1.md:106) — - resume requires Git-visible `governance/reviews/<review_id>.review.json`

### docs/specs/determinism_evidence.schema.v0.1.json
- none

### docs/specs/execution-permit-attestation-contract-v0.1.md
- docs/specs/review_ref.review_id (docs/specs/execution-permit-attestation-contract-v0.1.md:93) — - `review_ref.review_id`
- docs/specs/review_ref.review_type (docs/specs/execution-permit-attestation-contract-v0.1.md:94) — - `review_ref.review_type`
- docs/specs/secure_execution_layer.execution_permit.v1 (docs/specs/execution-permit-attestation-contract-v0.1.md:25) — - `secure_execution_layer.execution_permit.v1`
- governance/reviews/<review_id>.review.json (docs/specs/execution-permit-attestation-contract-v0.1.md:102) — - `governance/reviews/<review_id>.review.json` MUST exist in the evaluated Git state.

### docs/specs/execution-permit-attestation-contract-v0.1.schema.json
- none

### docs/specs/policy-to-capability-deterministic-mapping-contract-v0.1.md
- none

### docs/specs/policy-to-capability-mapping-v0.1.schema.json
- none

### docs/specs/secure-execution-layer-v0.2-milestone-notes.md
- none

### docs/specs/self_improvement_proposal.v0.1.md
- docs/specs/determinism_evidence.json (docs/specs/self_improvement_proposal.v0.1.md:58) — - `determinism_evidence.json`: `<path-or-tbd>`

### docs/specs/self_improvement_risk_tiers.v0.1.md
- none

### docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md
- docs/specs/event_type = "permit.issued (docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md:58) — - `event_type = "permit.issued"`.
- docs/specs/secure_execution_layer.execution_permit.v1 (docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md:55) — - Domain: `secure_execution_layer.execution_permit.v1`.
- governance/reviews/<review_id>.review.json (docs/specs/supervisor-execution-permit-issuance-flow-v0.1.md:80) — 2. Verify `governance/reviews/<review_id>.review.json` exists in evaluated Git state.

### docs/specs/supervisor-execution-permit-issuance-v0.1.schema.json
- none

### docs/supervisor-autonomy.v0.2.md
- docs/approvals/capabilities/revoke/<revoke_id>.approved (docs/supervisor-autonomy.v0.2.md:13) — - Requires approval marker at `approvals/capabilities/revoke/<revoke_id>.approved`.
- docs/requests/capabilities/revoke/<timestamp>__<capability>__<reason_slug>.json (docs/supervisor-autonomy.v0.2.md:8) — - Writes revoke request artifact at `requests/capabilities/revoke/<timestamp>__<capability>__<reason_slug>.json`.
- docs/scheduler.job_due (docs/supervisor-autonomy.v0.2.md:60) — - Emits `scheduler.job_due` events in lexical `job_id` order.
- state/supervisor_capability_denies.json (docs/supervisor-autonomy.v0.2.md:31) — Phase F optionally supports `state/supervisor_capability_denies.json`:

### docs/supervisor-governance-enforcement-v0.1.md
- docs/agents/state/environment.json (docs/supervisor-governance-enforcement-v0.1.md:47) — `docs/governance.md` and `agents/state/environment.json`
- state/environment.json (docs/supervisor-governance-enforcement-v0.1.md:47) — `docs/governance.md` and `agents/state/environment.json`

### docs/wiki-snapshot-hash.json
- none

### governance/night-queue.yaml
- none

### governance/policy/notifier/telegram/plugin.yaml
- none

### governance/policy/plugin-manifest.v0.1.yaml
- none

### governance/policy/plugins/plugin-boundary.v0.1.yaml
- none

### governance/policy/pr-governance.v0.2.yaml
- none

### governance/policy/skills/skills.v0.1.yaml
- none

### governance/schema/plugins/plugin-manifest.v0.1.yaml
- none

### governance/schema/scheduler/job.v0.1.json
- none

### governance/schema/supervisor/capability-revoke.v0.1.json
- supervisor/capability-revoke.v0.1.json (governance/schema/supervisor/capability-revoke.v0.1.json:3) — "$id": "https://ai-os.local/schema/supervisor/capability-revoke.v0.1.json",

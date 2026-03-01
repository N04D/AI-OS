# Codex Autonomy Progress Log

Status: active
Current Phase: 5 (Autonomous Night-Run Integration)
Current Focus: Phase 5 Extension complete

## 2026-02-27

- Completed:
  - Removed implicit `origin` assumptions from runtime paths:
    - `supervisor/environment_validation.py`
    - `supervisor/supervisor.py`
    - `supervisor/pr_gate/gitea_client.py`
    - `orchestrator/git.py`
    - `scripts/night-bootstrap.sh`
  - Added shared remote resolver:
    - `supervisor/git_remote.py`
  - Removed broad staging in orchestrator commit flow:
    - `orchestrator/git.py` (`commit()` now stages explicit files)
    - `orchestrator/commit_flow.py` (passes explicit changed file list)
  - Added mutation-boundary test for allowlist enforcement:
    - `tests/test_mutation_boundary.py`
  - Added deterministic JSON serialization regression tests:
    - `tests/test_state_json_determinism.py`
  - Enforced strict UTC-only handling in scheduler/budgets:
    - `supervisor/budgets/store.py`
    - `supervisor/scheduler/config.py`
  - Restored deterministic night-mode testability across environments:
    - policy path resolution fallback via `resolve_policy_path(...)`
    - robust Gitea response status handling for mocked/nonstandard responses
    - updated preflight policy resolution in `supervisor/cli.py`
  - Reduced legacy budget overlap in runtime execution path:
    - `supervisor/night_executor.py` now uses `supervisor.autonomy_budget` via a compatibility adapter (`check_and_consume`)
    - removed direct runtime dependency on `supervisor.autonomy_budget_gate` internals
  - Added explicit redundancy evidence:
    - `docs/roadmap/autonomy_budget_gate_redundancy_proof.md`
    - dependency scan confirms no runtime imports
    - behavior equivalence check captured for compatibility API
  - Removed redundant compatibility module and module-specific test:
    - removed `supervisor/autonomy_budget_gate.py`
    - removed `supervisor/tests/test_autonomy_budget_gate.py`
  - Consolidated legacy autonomy budget path into canonical budgets namespace:
    - added `supervisor/budgets/autonomy.py`
    - updated runtime and gate imports to `supervisor.budgets.autonomy`
    - removed `supervisor/autonomy_budget.py`
  - Added fail-closed budget corruption regression test:
    - `supervisor/tests/test_autonomy_budget.py::test_invalid_state_file_fails_closed`
  - Added UTC enforcement regression tests:
    - `tests/test_utc_enforcement.py`
  - Added tests for remote/staging behavior:
    - `tests/test_git_remote.py`
    - `tests/test_orchestrator_git_remote.py`

- Validation notes:
  - `pytest` is available via `/home/n04d/.local/bin/pytest`.
  - Targeted roadmap suite status:
    - `38 passed` on supervisor gate/runtime suites
    - `25 passed` on night/scheduler/budget suites
    - `63 passed` combined for this phase-close run set
  - Dependency scan checks:
    - no production imports remain for `supervisor.autonomy_budget` or `supervisor.autonomy_budget_gate`
  - Syntax checks passed with:
    - `PYTHONPYCACHEPREFIX=/tmp/aios-pyc python3 -m py_compile ...`

- Next item in progress:
  - `Phase 2 — Deterministic Night Autonomy`

## Phase 2 Closeout (2026-02-27)

- Completed objectives:
  - Night mode executes full autonomy loop.
  - Scheduler deterministic ordering confirmed.
  - Budget consumption recorded deterministically.
  - Status publication to Gitea verified.
  - No non-deterministic timestamps outside controlled areas.

- Added/updated Phase 2 evidence tests:
  - `tests/test_night_mode.py::test_three_consecutive_night_runs_succeed`
  - `tests/test_night_mode.py::test_identical_output_for_identical_state`
  - `tests/test_night_mode.py::test_summary_has_only_controlled_time_field`

- Validation criteria evidence:
  - 3 consecutive successful night runs: covered by `test_three_consecutive_night_runs_succeed`.
  - Identical output for identical state: covered by `test_identical_output_for_identical_state`.
  - Audit artifacts produced consistently: ledger equality assertion in `test_identical_output_for_identical_state`.
  - No governance bypass possible: covered by existing fail-closed tests in `tests/test_night_mode.py` (`DENY_*` paths).

- Test execution:
  - Targeted Phase 2 suite: `29 passed` (`tests/test_night_mode.py`, scheduler, budget suites).
  - `tests/test_night_mode.py`: `20 passed`.
  - Full suite (`pytest -q`): `11 failed, 352 passed, 14 skipped`.
  - Full-suite failures are outside Phase 2 scope and environment-bound:
    - plugin loader tests require `python` executable on PATH
    - Phase-K budget tests require `/home/infra/AI-OS/governance_policy.yaml`

- State:
  - Phase 2 objectives complete.
  - HALT.

## Remediation Closeout (2026-02-27)

- Conditional-acceptance remediation completed:
  - plugin-loader tests now use `sys.executable` (environment-agnostic process launch)
  - Phase-K policy tests now resolve policy path dynamically
  - explicit skip reason added when policy file is unavailable in environment

- Full suite status after remediation:
  - `363 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 2 Acceptance (2026-02-27)

- Roadmap status update applied:
  - `Phase 2: ACCEPTED`

## Phase 3 Kickoff (2026-02-27)

- Scope activated:
  - `Phase 3 – Supervisor Hardening & Control Plane`
- Execution mode:
  - roadmap execution plan added with 10 tracked steps
- Current implementation stream:
  - 3.1 Approval Token Mechanism (Hard Gate)

## Phase 3.1 Progress (2026-02-27)

- Implemented:
  - added supervisor token validation module: `supervisor/approval_tokens.py`
  - token model enforced as scope-bound, time-bound, single-use
  - SHA256 token hash logging added to audit stream (`logs/control/approval_token_audit.jsonl`)
  - deterministic deny reasons for missing/expired/reused/invalid-scope tokens
  - supervisor integration points:
    - phase start gate (`SUPERVISOR_PHASE_START_TOKEN`)
    - high-risk autonomy gate (`SUPERVISOR_HIGH_RISK_TOKEN`)
    - budget override gate (`SUPERVISOR_BUDGET_OVERRIDE_TOKEN`)
- Added tests:
  - `supervisor/tests/test_approval_tokens.py`
  - updated `supervisor/tests/test_cli.py` for budget reset token enforcement
- Verification:
  - targeted run: `9 passed` (`supervisor/tests/test_approval_tokens.py`, `supervisor/tests/test_cli.py`)

## Phase 3.2 Progress (2026-02-27)

- Implemented deterministic interrupt handling:
  - added interrupt checks in night-mode control flow:
    - phase boundary
    - before budget consume
  - added scheduler tick interrupt gate:
    - interrupt check at tick start
    - interrupt check before guarded budget consume
  - added HALT persistence in autonomy state:
    - `HALT_STATE` with reason/checkpoint/timestamp
  - added interrupt audit artifacts:
    - `logs/control/interrupts/<date>/interrupt__<checkpoint>.json`
- Added tests:
  - `tests/test_night_mode.py` (phase-boundary + pre-budget interrupt halt)
  - `tests/test_aiosctl_scheduler_tick.py` (scheduler tick interrupt halt)
- Verification:
  - targeted run: `25 passed` (`tests/test_night_mode.py`, `tests/test_aiosctl_scheduler_tick.py`)
  - full suite: `371 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 3.3 Progress (2026-02-27)

- Implemented canonical supervisor control-plane boundary:
  - added `supervisor/control_plane.py` as import boundary for:
    - budget engine + budget consume path
    - scheduler load/compute/dispatch path
    - task materialization path
  - refactored runtime imports to boundary interface in:
    - `supervisor/cli.py`
    - `autonomy_orchestrator/night_mode.py`
    - `orchestrator/git.py`
- Added static boundary scan enforcement:
  - `tests/test_supervisor_boundary_imports.py`
  - fails if direct governance-core imports are introduced outside boundary
  - includes explicit assertion that executor cannot import budget core directly
- Verification:
  - targeted run: `34 passed` (boundary + touched suites)
  - full suite: `373 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 3.4 Progress (2026-02-27)

- Implemented state integrity verification:
  - added `supervisor/state_integrity.py`
    - SHA256 hashing for autonomy + budget state
    - controlled metadata baseline/reference storage
    - fail-closed verification before execution
    - deterministic integrity audit log entries
  - integrated verification into:
    - night mode pre-execution flow (`autonomy_orchestrator/night_mode.py`)
    - scheduler tick pre-execution flow (`supervisor/cli.py`)
  - added controlled reference-hash update after successful governed state transitions
  - added deterministic bootstrap of missing autonomy state (`INTERRUPT_FLAG=false`) for first-run baseline

- Added tests:
  - `supervisor/tests/test_state_integrity.py`
  - `tests/test_night_mode.py::test_night_mode_denies_on_budget_state_tamper`
  - `tests/test_aiosctl_scheduler_tick.py::test_scheduler_tick_denies_when_budget_state_is_tampered`

- Verification:
  - targeted run: `29 passed` (integrity + night mode + scheduler tick suites)
  - additional touched suites: `11 passed`
  - full suite: `377 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 3.5 Completion (2026-02-27)

- Implemented permanent phase acceptance rule:
  - canonical governance document:
    - `docs/phase-acceptance-rule.v0.1.md`
  - deterministic verification module:
    - `supervisor/phase_acceptance.py`
  - fail-closed CLI guard:
    - `aiosctl autonomy phase-acceptance verify --evidence-path <json>`
    - wired in `supervisor/cli.py`
- Automated proof tests (negative + positive):
  - `supervisor/tests/test_phase_acceptance.py`
  - `supervisor/tests/test_cli.py` (phase-acceptance verify command paths)
- Acceptance evidence recorded:
  - `state/supervisor/phase3_5_acceptance_evidence.json`
  - verification command output status: `ok`

- Final verification:
  - full suite: `385 passed, 14 skipped, 0 failed` (`pytest -q`)
  - skip justifications captured explicitly in acceptance evidence (14/14)

- State:
  - Phase 3.5 objectives complete.
  - HALT.

## Phase 4.1 Progress (2026-02-27)

- Implemented PR-only self-improvement proposal pipeline hooks:
  - added canonical proposal template:
    - `docs/specs/self_improvement_proposal.v0.1.md`
  - extended PR gate evaluator with self-improvement checks:
    - required `self-improvement` label in self-improvement context
    - required proposal sections (problem, risk, components, determinism, test plan, rollback)
    - required explicit risk tier (LOW/MED/HIGH)
    - required deterministic test plan section presence
    - required checklist markers in PR body
    - required supervisor status context success for self-improvement PRs
  - added dedicated tests:
    - `tests/test_self_improvement_pipeline.py`
  - fixed section-heading parser regression to keep markdown-bypass guard intact.

- Verification:
  - targeted gate suites: `26 passed`
  - markdown + self-improvement suites: `7 passed`
  - full suite: `389 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 4.2 Progress (2026-02-27)

- Implemented hard boundary constraints in PR gate for self-improvement context:
  - allowlist enforcement (`docs/`, `tests/`, and proposal-declared runtime scope)
  - disallowed path fail-closed behavior
  - governance-core restriction requiring HIGH tier
  - runtime-change requires test-update enforcement
- Extended self-improvement test coverage:
  - disallowed path denied
  - runtime change without tests denied
  - governance-core edit without HIGH tier denied
  - declared runtime scope + tests positive path

- Verification:
  - targeted suites: `18 passed`
  - full suite: `393 passed, 14 skipped, 0 failed` (`pytest -q`)

- Static boundary scan extension completed:
  - deterministic boundary scan helper added in PR gate evaluator
  - dedicated static boundary scan tests added:
    - `tests/test_self_improvement_boundary_scan.py`

- Verification update:
  - boundary scan + pipeline suites: `11 passed`
  - full suite: `396 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 4.3 Progress (2026-02-27)

- Implemented risk-tier and token gating:
  - canonical risk tier spec:
    - `docs/specs/self_improvement_risk_tiers.v0.1.md`
  - proposal template extended with:
    - `Determinism Evidence` section
    - `Approval Token` section (HIGH only)
  - PR gate enforcements added for self-improvement context:
    - MED/HIGH requires determinism evidence
    - HIGH requires approval token evidence
    - audit record emits `risk_tier` + `decision` in evaluator output (`self_improvement_audit`)
- Added/updated tests:
  - `tests/test_self_improvement_pipeline.py`
  - `tests/test_self_improvement_boundary_scan.py`
- Verification:
  - targeted suites: `20 passed`
  - full suite: `398 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 4.4 Progress (2026-02-27)

- Implemented determinism evidence guardrails:
  - schema artifact added:
    - `docs/specs/determinism_evidence.schema.v0.1.json`
  - deterministic verifier module added:
    - `supervisor/determinism_evidence.py`
  - fail-closed CLI guard added:
    - `aiosctl autonomy determinism-evidence verify --path <json>`
  - PR-gate MED/HIGH enforcement uses determinism evidence requirement.

- Added tests:
  - `supervisor/tests/test_determinism_evidence.py`
  - `supervisor/tests/test_cli.py` (determinism-evidence command coverage)

- Verification:
  - targeted suites: `23 passed`
  - full suite: `403 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 4.5 Progress (2026-02-27)

- Implemented improvement budget accounting:
  - added `improvement` budget category in `supervisor/budgets/autonomy.py`
  - added deterministic consumption helper:
    - `consume_improvement_budget(pr_id, tier, ...)`
  - added explicit audit linkage event:
    - `improvement_budget_consume` with `pr_id` + `tier`
  - added CLI controls:
    - `aiosctl autonomy improvement-budget status`
    - `aiosctl autonomy improvement-budget consume --pr-id --tier`

- Added/updated tests:
  - `supervisor/tests/test_autonomy_budget.py`
  - `supervisor/tests/test_cli.py`

- Verification:
  - targeted suites: `32 passed`
  - full suite: `408 passed, 14 skipped, 0 failed` (`pytest -q`)

## Phase 4.6 / 4.7 / 4.8 Progress (2026-02-27)

- Implemented additional self-improvement governance gates in PR evaluator:
  - `self_improvement_pr_only_mutation`
  - `self_improvement_phase_acceptance_required`
  - `self_improvement_halt_discipline`
- Extended proposal evidence enforcement:
  - phase acceptance evidence must include:
    - `0 failed`
    - `skip justifications`
    - `roadmap update`
    - `progress update`
    - `HALT`
  - HALT discipline evidence must include:
    - `HALT entered`
    - `authorization required`
- Added/updated tests:
  - `tests/test_self_improvement_pipeline.py`
    - positive full-proposal pass case updated
    - negative test for runtime mutation outside governed self-improvement PR
    - negative test for missing phase-acceptance evidence
    - negative test for missing HALT-discipline evidence

- Verification:
  - targeted suites: `16 passed` (`tests/test_self_improvement_pipeline.py`, `tests/test_self_improvement_boundary_scan.py`)
  - full suite: `411 passed, 14 skipped, 0 failed` (`pytest -q`)

- State:
  - Phase 4 governance gates for 4.6 and 4.7 enforced with deterministic deny behavior.
  - Phase 4.8 partially enforced at PR-gate evidence level.
  - HALT.

## Phase 4.4 + 4.8 Completion (2026-02-27)

- 4.4 Determinism guardrails completed:
  - extended determinism evidence tests in:
    - `supervisor/tests/test_determinism_evidence.py`
  - added validations for:
    - identical-input -> identical verification output
    - uncontrolled timestamp field rejection (`created_at` denied)
    - HIGH-tier rerun-consistency enforcement
    - no wall-clock imports (`datetime`/`time`) in determinism verifier
  - added PR gate validation test that MED self-improvement with determinism evidence satisfies requirement.

- 4.8 HALT discipline completed:
  - extended PR gate in `supervisor/pr_gate/evaluator.py` with:
    - stricter HALT discipline evidence tokens:
      - `halt entered`
      - `authorization required`
      - `awaiting approval`
      - `no commits beyond proposal`
    - post-proposal commit authorization gate:
      - `self_improvement_post_proposal_authorization`
    - deterministic HALT audit state fields:
      - `halt_state`
      - `awaiting_approval_logged`
  - extended tests in `tests/test_self_improvement_pipeline.py`:
    - awaiting-approval state logged in positive path
    - post-proposal commits denied without authorization
    - post-proposal commits allowed with explicit authorization token

- Verification:
  - targeted suites: `26 passed`
  - full suite: `418 passed, 14 skipped, 0 failed` (`pytest -q`)

- State:
  - Phase 4.4 complete.
  - Phase 4.8 complete.
  - HALT.

## Phase 4 Exit Evidence (2026-02-27)

- Negative-proof references:
  - Governed PR flow required:
    - `tests/test_self_improvement_pipeline.py:153`
    - deny gate: `self_improvement_pr_only_mutation`
  - Risk tier bypass denied:
    - `tests/test_self_improvement_pipeline.py:517`
    - deny gate: `self_improvement_risk_tier`
  - HIGH-risk without approval token denied:
    - `tests/test_self_improvement_pipeline.py:631`
    - deny gate: `self_improvement_high_risk_token_required`
  - Runtime improvement budget enforcement:
    - `supervisor/tests/test_cli.py:306`
    - deny reason: `budget_exceeded`

- Full suite verification:
  - `422 passed, 14 skipped in 23.67s` (`pytest -q`)

- State:
  - Phase 4 closure evidence recorded.
  - HALT.

## Phase 5 Completion (2026-02-27)

- Implemented autonomous night-run issue loop integration:
  - deterministic queue recheck loop for Gitea issues
  - sequential issue processing with deterministic ordering
  - deterministic HALT when queue is exhausted
  - per-issue audit artifacts:
    - detected
    - materialized
    - resolved

- Implemented capability handling hardening:
  - missing capability now emits `capability_request` artifact:
    - `requests/capabilities/night_mode/<epoch>__issue_<id>__<task_hash>.json`
  - capability request is auditable via issue-audit records
  - self-improvement execution now requires explicit supervisor token:
    - env: `SUPERVISOR_CAPABILITY_EXECUTION_TOKEN`
    - deny path is fail-closed on missing/invalid token
  - no silent auto-grant path verified (capability ledger remains unchanged on denial)

- Implemented governed execution controls for self-improvement issues:
  - explicit risk-tier label required (`risk:low|risk:med|risk:high`) for self-improvement issues
  - improvement budget enforced at runtime per processed self-improvement task
  - determinism evidence artifact generated for runtime-affecting MED/HIGH tasks

- Added/updated tests:
  - `tests/test_night_mode.py`
    - `test_gitea_issue_queue_recheck_is_deterministic_and_halts_when_empty`
    - `test_missing_capability_writes_capability_request_artifact`
    - `test_self_improvement_capability_execution_denied_without_token`
    - `test_self_improvement_missing_risk_label_is_denied`
    - `test_self_improvement_med_runtime_generates_determinism_evidence`
    - `test_self_improvement_runtime_enforces_improvement_budget_limit`
  - adjusted existing lifecycle expectation:
    - `test_gitea_issue_lifecycle_success_flow` now validates deterministic HALT on empty queue

- Verification:
  - targeted suite: `29 passed` (`tests/test_night_mode.py`)
  - full suite: `428 passed, 14 skipped in 27.36s` (`pytest -q`)

- State:
  - Phase 5 roadmap objectives and validation criteria implemented and tested.
  - HALT.

## Phase 5 Extension Completion (2026-02-27)

- Implemented local deterministic intake mode for night-run:
  - local queue source:
    - `state/issues/open/*.json`
    - `state/issues/open/*.md`
  - strict deterministic ordering by filename
  - fail-closed schema validation (no implicit defaults)
  - sequential processing with queue re-check after each issue
  - deterministic HALT when queue is empty

- Implemented local capability registry and request enforcement:
  - explicit registry:
    - `state/capabilities/enabled.json`
  - missing required capability emits request artifact:
    - `state/capability_requests/<epoch>__<issue_id>__<capability>.json`
  - execution denied on missing capability (no auto-grant, no fallback)

- Evidence tests:
  - hello world via governed flow:
    - `tests/test_night_mode_local_intake.py::test_local_hello_world_issue_creates_file_and_halts`
  - missing email capability -> request + deny:
    - `tests/test_night_mode_local_intake.py::test_local_email_issue_missing_capability_emits_request_and_denies`
  - deterministic queue re-check + HALT on empty:
    - `tests/test_night_mode_local_intake.py::test_local_queue_recheck_processes_in_order_and_halts_when_empty`

- Verification:
  - targeted suites: `32 passed`
    - `tests/test_night_mode_local_intake.py`
    - `tests/test_night_mode.py`
  - full suite: `431 passed, 14 skipped in 27.04s` (`pytest -q`)

- State:
  - Phase 5 Extension objectives complete.
  - HALT.

## Phase 7C Progress (2026-02-28)

- Implemented remote replay protection in runtime:
  - persistent ledger path:
    - `state/issues/remote/remote_issue_execution_ledger.json`
  - remote replay deny code:
    - `DENY_ALREADY_EXECUTED`
  - replay audit artifact:
    - `logs/control/night_issue_audit/<epoch>/<issue_id>__replay_denied.json`

- Added/updated remote integrity test coverage:
  - `tests/test_night_mode_remote_sync.py::test_remote_issue_replay_denied_by_execution_ledger`
  - `tests/test_night_mode_remote_sync.py::test_remote_risk_tier_detection_is_deterministic_for_low_med_high`
  - `tests/test_night_mode_remote_sync.py::test_source_both_merge_order_is_stable`
  - `tests/test_night_mode_remote_sync.py::test_source_both_fetch_order_is_deterministic_across_repeated_runs`
  - `tests/test_night_mode_remote_sync.py::test_remote_401_fails_closed_without_partial_intake`
  - `tests/test_night_mode_remote_sync.py::test_remote_429_rate_limit_fails_closed`
  - `tests/test_night_mode_remote_sync.py::test_remote_invalid_json_fails_closed`
  - `tests/test_night_mode_remote_sync.py::test_remote_high_inline_override_attempt_is_ignored`
  - `tests/test_night_mode_remote_sync.py::test_remote_high_with_token_but_missing_capability_still_denied`
  - `tests/test_night_mode_remote_sync.py::test_remote_budget_enforcement_denies_second_issue`

- Verification:
  - targeted suites:
    - `17 passed in 3.52s`
      - `pytest -q tests/test_night_mode_remote_sync.py tests/test_night_mode_local_intake.py`
    - `20 passed in 5.26s`
      - `pytest -q tests/test_night_mode_remote_sync.py tests/test_night_mode_local_intake.py`
  - full suite:
    - `448 passed, 14 skipped in 40.88s`
      - `pytest -q`
    - `450 passed, 14 skipped in 30.08s`
      - `pytest -q`

- State:
  - Phase 7C execution plan steps 1-8 completed.
  - HALT pending after remaining 7C closure checks.

## Phase 7C Determinism Hard Proof Sync (2026-02-28, epoch: 2026-02-27 / 2026-02-28)

- Evidence pointers:
  - `tests/test_night_mode_remote_sync.py::test_determinism_hard_proof_same_epoch_byte_identical_artifacts`
  - `tests/test_night_mode_remote_sync.py::test_determinism_cross_epoch_only_epoch_field_differs`
  - `tests/test_night_mode_remote_sync.py::test_merge_order_proof_stable_when_creation_order_is_shuffled`
  - `tests/test_night_mode_remote_sync.py::test_regression_no_new_nondeterministic_fields_in_artifact_roots`

- Latest verification summary:
  - `pytest -q` -> `454 passed, 14 skipped in 39.28s`

- State:
  - Phase 7C roadmap checkboxes aligned with deterministic hard-proof evidence.
  - Step 9 (Enter HALT) recorded as complete.
  - HALT.

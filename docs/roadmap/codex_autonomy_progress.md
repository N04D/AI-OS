# Codex Autonomy Progress Log

Status: active
Current Phase: 1 (Runtime Consolidation)
Current Focus: Remove `autonomy_budget_gate.py` in separate commit

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
  - Added UTC enforcement regression tests:
    - `tests/test_utc_enforcement.py`
  - Added tests for remote/staging behavior:
    - `tests/test_git_remote.py`
    - `tests/test_orchestrator_git_remote.py`

- Validation notes:
  - `pytest` is available via `/home/n04d/.local/bin/pytest`.
  - Targeted roadmap suite status:
    - `56 passed` (including `tests/test_night_mode.py`, `supervisor/tests/test_autonomy_budget_gate.py`, `supervisor/tests/test_night_executor.py`)
  - Syntax checks passed with:
    - `PYTHONPYCACHEPREFIX=/tmp/aios-pyc python3 -m py_compile ...`

- Next item in progress:
  - `Remove autonomy_budget_gate.py in separate commit`

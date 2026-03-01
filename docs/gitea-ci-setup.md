# Gitea CI Setup for PR-Gate Path Allowlist

## Purpose
Configure Gitea Actions and branch protection so PR merges are blocked unless path-allowlist gate passes.

## Workflow
- File: `.gitea/workflows/pr-gate.yml`
- Trigger: pull request events (`opened`, `synchronize`, `reopened`)
- Check names:
  - Required: `pr-gate/path-allowlist`
  - Recommended: `pr-gate/path-allowlist-contracts`
- Evaluator: `scripts/pr_gate_path_allowlist.py`

The workflow is fail-closed:
- Missing token, missing API base, event parse errors, policy errors, or API errors all produce non-zero exit and fail the check.

## Required Repository Settings

### 0) Prerequisites
- Gitea Actions must be enabled for the repository/instance.
- At least one runner must be available for `ubuntu-latest` and support container jobs.

### 1) Add secret
- Name: `PR_GATE_TOKEN`
- Scope: token must be able to read pull request metadata/files in the repository.

### 2) Add variable (recommended)
- Name: `PR_GATE_API_BASE`
- Value: your Gitea API base, for example:
  - `https://gitea.example.com/api/v1`

If omitted, workflow falls back to `GITEA_SERVER_URL/api/v1` when `GITEA_SERVER_URL` is available.

### 3) Configure branch protection
For protected branches (for example `main`):
- Enable required status checks.
- Add required check with exact name:
  - `pr-gate/path-allowlist`
- Optional but recommended additional check:
  - `pr-gate/path-allowlist-contracts`

Merges must be blocked unless this check succeeds.

## Policy Location
- `.gitea/governance/path-allowlist.v1.yaml`

Current default policy is logs-only and deny-by-default.

## Determinism and Audit Notes
- Evaluator fetches changed files from PR files API only.
- Policy is read from versioned repository file.
- Output verdict artifact:
  - `gate-verdict.json`
- Deny outcomes include explicit `reason_code` values.

## Local Validation
Run the Milestone 1 contract suite:

```bash
bash scripts/test-pr-gate-m1.sh
```

This executes:
- evaluator tests
- workflow contract tests
- docs/workflow drift tests

## Troubleshooting (Fail-Closed)
| Symptom | Expected Behavior | Reason Code |
|---|---|---|
| `PR_GATE_TOKEN` missing | Workflow fails immediately, merge blocked | `DENY_WORKFLOW_MISSING_TOKEN` |
| API base unavailable (`PR_GATE_API_BASE` and `GITEA_SERVER_URL` both missing) | Workflow fails immediately, merge blocked | `DENY_WORKFLOW_MISSING_API_BASE` |
| Policy file missing | Evaluator exits non-zero, merge blocked | `DENY_POLICY_MISSING` |
| Policy parse error | Evaluator exits non-zero, merge blocked | `DENY_POLICY_PARSE_ERROR` |
| PR files API error | Evaluator exits non-zero, merge blocked | `DENY_GITHUB_API_ERROR` |

Workflow always emits `gate-verdict.json` and prints it in logs via the `Emit gate verdict` step.

# PR-Gate Path Allowlist v0.1

## What It Does
This gate enforces a strict path allowlist for pull requests, fail-closed:

- Policy file: `.gitea/governance/path-allowlist.v1.yaml`
- Default decision: `deny`
- A PR is allowed only when **every changed file** matches at least one allowed glob.

Current default policy is logs-only:

```yaml
rules:
  - id: allow-logs-only
    allow:
      paths:
        - "logs/**"
```

## Workflow
Workflow file: `.github/workflows/pr-gate-path-allowlist.yml`

Trigger:
- `pull_request` on `opened`, `synchronize`, `reopened`

Job/check name:
- `pr-gate/path-allowlist`

Behavior:
1. Runs `scripts/pr_gate_path_allowlist.py`
2. Fetches PR changed files from GitHub API (`GET /repos/{owner}/{repo}/pulls/{number}/files`)
3. Loads and evaluates `.gitea/governance/path-allowlist.v1.yaml`
4. Writes `gate-verdict.json`
5. Uploads `gate-verdict.json` as workflow artifact
6. Exits non-zero for deny/error (fail-closed)

## Verdict Artifact
The evaluator writes `gate-verdict.json`:

```json
{
  "allow": false,
  "reason_code": "DENY_PATH_VIOLATION",
  "violations": ["src/app.py"],
  "matched_rule_ids": ["allow-logs-only"],
  "policy_sha": "<sha256>",
  "evaluated_at": "2026-02-23T16:00:00Z"
}
```

Reason codes:
- `ALLOW_ALL_PATHS_MATCH`
- `DENY_PATH_VIOLATION`
- `DENY_POLICY_MISSING`
- `DENY_POLICY_PARSE_ERROR`
- `DENY_INVALID_POLICY_DEFAULT`
- `DENY_GITHUB_API_ERROR`
- `DENY_EVALUATOR_ERROR`

## Branch Protection Setup
To enforce this gate on `main`:

1. Open repository settings -> Branch protection rules.
2. Add or edit the `main` branch rule.
3. Enable required status checks.
4. Add required check: `pr-gate/path-allowlist` (exact name).
5. Save.

With this enabled, merges are blocked unless this gate passes.

## Determinism and Fail-Closed Notes
- Deterministic input: sorted changed file paths from GitHub PR files API.
- Deterministic evaluation: glob matching against versioned YAML policy.
- Missing/invalid policy always denies.
- Evaluator runtime/API errors always deny.
- Workflow failure blocks merge when the check is required.

# Path Allowlist Policy v0.1

## Purpose
Specify a versioned, deterministic, fail-closed allowlist policy used by PR-Gate to decide whether job-generated PRs may merge.

## Baseline Pattern Observed
Reference snippets:
- `templates/.github/workflows/auto-merge.yml:55` reads `ALLOWED_PATHS` variable.
- `templates/.github/workflows/auto-merge.yml:60` defaults to `/logs`.
- `templates/.github/workflows/auto-merge.yml:112` merge executes only after checks.

## Policy File Format (YAML)
Canonical path: `.gitea/governance/path-allowlist.v1.yaml` (or repo-defined equivalent).

```yaml
version: 1
policy_id: path-allowlist-v0.1
mode: enforce
applies_to:
  branch_prefixes:
    - "job/"
  base_branches:
    - "main"
default_decision: deny
rules:
  - id: allow-job-logs
    allow:
      paths:
        - "logs/**"
  - id: allow-job-results
    allow:
      paths:
        - "artifacts/jobs/**"
exceptions: []
```

## Policy Semantics
- Match evaluation target: normalized repository-relative changed file paths from PR diff.
- Policy evaluation is deterministic and side-effect free.
- `default_decision: deny` is mandatory.
- Any parse error, missing file, or unknown version => deny.

## PR-Gate Evaluator Contract
Input:
```json
{
  "pr_number": 42,
  "head_ref": "job/123",
  "base_ref": "main",
  "changed_files": ["logs/123/job.md", "src/app.ts"],
  "policy_path": ".gitea/governance/path-allowlist.v1.yaml",
  "policy_sha": "..."
}
```

Output:
```json
{
  "allow": false,
  "reason_code": "PATH_VIOLATION",
  "violations": ["src/app.ts"],
  "matched_rule_ids": ["allow-job-logs"],
  "policy_sha": "..."
}
```

Status publishing:
- Required status check name: `pr-gate/path-allowlist`.
- Merge is blocked unless status is `success`.

## Versioning and Change Management
Policy changes MUST be:
1. Proposed via PR.
2. Reviewed by code owners of governance path.
3. Applied only after PR merge.
4. Referenced by `policy_sha` in gate output.

Recommended controls:
- Protect policy file path with CODEOWNERS.
- Require signed commits for policy changes.
- Require two-person review for widening allowlist.

## Example Rules and Edge Cases
### Example: Strict logs-only
```yaml
default_decision: deny
rules:
  - id: logs-only
    allow:
      paths: ["logs/**"]
```

### Example: Allow generated reports
```yaml
rules:
  - id: logs
    allow: { paths: ["logs/**"] }
  - id: reports
    allow: { paths: ["reports/generated/**"] }
```

### Edge Cases
| Case | Expected Decision |
|---|---|
| Empty diff | deny (unless explicitly allowed by policy) |
| File rename out of allowlist | deny |
| Path traversal patterns (`../`) | normalize then deny if invalid |
| Symlink target escapes allowlist | deny |
| Policy file missing | deny |
| Unknown policy `version` | deny |

## Merge Gating Semantics
Gate must evaluate on:
- PR `opened`
- PR `synchronize`
- PR `reopened`

Terminal rule:
- If latest gate verdict is not explicit allow, merge is forbidden.

Determinism requirements:
- Same `(policy_sha, diff)` => same verdict.
- Include sorted file list in evaluator evidence payload.

## GitHub Actions Compatibility
The baseline workflow currently enforces allowlist in shell using repo variable (`ALLOWED_PATHS`).

Compatibility plan:
1. Keep `job/*` branch strategy unchanged.
2. Replace/augment shell check with PR-Gate evaluator step.
3. Make PR-Gate status required branch protection.
4. Optionally keep `AUTO_MERGE` as coarse kill switch, but never as sole policy.

Suggested workflow integration point:
- Existing `templates/.github/workflows/auto-merge.yml` before merge step.
- Replace variable parsing with evaluator invocation + required status.

## Compatibility with PR-Gate Design
| Dimension | Baseline (`AUTO_MERGE` + `ALLOWED_PATHS`) | Path Allowlist v0.1 |
|---|---|---|
| Policy storage | Mutable repo variables | Versioned YAML in repo |
| Evaluation | Inline shell script | Dedicated deterministic evaluator |
| Auditability | Workflow logs only | Structured verdict with `policy_sha` |
| Failure behavior | Partial/implicit | Explicit fail-closed |
| Reproducibility | Medium | High (policy + diff deterministic) |

## Required Artifacts
For each evaluated PR, persist:
- `logs/<job_id>/gate-input.json`
- `logs/<job_id>/gate-verdict.json`
- ledger event `gate.verdict`

Example `gate-verdict.json`:
```json
{
  "allow": true,
  "reason_code": "ALLOW",
  "violations": [],
  "policy_sha": "...",
  "evaluated_at": "2026-02-23T16:00:00Z"
}
```


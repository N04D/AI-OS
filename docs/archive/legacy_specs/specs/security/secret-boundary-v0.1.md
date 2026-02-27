# Secret Boundary v0.1

## Purpose
Define deterministic, auditable secret handling for autonomous job execution with strict tiering and fail-closed enforcement.

## Baseline Pattern Observed
Reference snippets:
- `templates/.github/workflows/run-job.yml:53` builds `SECRETS` from `AGENT_*`.
- `templates/.github/workflows/run-job.yml:58` builds `LLM_SECRETS` from `AGENT_LLM_*`.
- `templates/docker/job/entrypoint.sh:15` uses `eval $(...)` to export secrets.
- `templates/docker/job/entrypoint.sh:19` states LLM secrets are not filtered.

## Secret Tiers
| Tier | Purpose | Visible to LLM prompt/tool loop | Examples |
|---|---|---|---|
| `CONTROL_SECRETS` | Platform control/authN/authZ and infrastructure operations | No | Git provider token, webhook signing key |
| `TASK_SECRETS` | Explicitly granted task credentials needed for user-approved objective | Only if grant says so | API keys for target system, test credentials |

Normative rule: if classification is unknown, treat as `CONTROL_SECRETS` and deny LLM exposure.

## Exposure Policy Per Job (Capability Grants)
Each job MUST carry a secret exposure policy artifact.

```json
{
  "job_id": "uuid",
  "secret_grants": [
    {
      "name": "BRAVE_API_KEY",
      "tier": "TASK_SECRETS",
      "exposure": "llm_env",
      "scope": ["network:api.brave.com"],
      "expires_at": "2026-02-24T00:00:00Z",
      "justification": "user-approved web research"
    }
  ],
  "default_exposure": "deny"
}
```

Required semantics:
- No implicit grants.
- Grant must be job-bounded and time-bounded.
- Expired grants are ignored and logged as denied.

## Safe Injection Requirements (No Unsafe `eval`/bash export)
### Prohibited
- `eval $(...)` for secret export.
- Dynamic shell interpolation of secret values.

### Required
1. Secret material arrives in structured form (JSON) over trusted channel.
2. Runtime writes secrets to root-only env file (`0600`) with safe escaping.
3. Process supervisor loads env file directly (no shell eval).
4. Child-process environment is constructed from explicit allowlist.

Example safe loader pseudocode:
```text
parse JSON -> validate key regex -> write KEY=VALUE via robust encoder -> execve(process, env_map)
```

## Attestation and Logging Requirements
Each transition involving secrets MUST emit a ledger event with:
- `job_id`, `seq`, `timestamp`, `actor`
- `decision` (`granted|denied|expired|invalid`)
- `secret_name`, `tier`, `exposure_mode`
- `policy_sha`, `request_sha`
- `reason_code`

### Required Events
| Event | Description |
|---|---|
| `secret.policy.loaded` | Policy artifact accepted and hashed |
| `secret.grant.applied` | Grant mapped to runtime environment |
| `secret.grant.denied` | Request denied by default or rule |
| `secret.access.attempt` | Tool/runtime attempted access |
| `secret.access.blocked` | Boundary blocked access |

## Secret Boundary Table (Example)
| Secret | Tier | Default | Allowed Exposure | Logging |
|---|---|---|---|---|
| `GH_TOKEN` | CONTROL_SECRETS | Deny | `control_plane_only` | access attempts + deny |
| `GH_WEBHOOK_SECRET` | CONTROL_SECRETS | Deny | `signer_only` | signer usage only |
| `BRAVE_API_KEY` | TASK_SECRETS | Deny | `llm_env` if granted | grant + access |
| `TEST_APP_PASSWORD` | TASK_SECRETS | Deny | `tool:browser-login` if granted | grant + tool access |

## Recording Secret Exposure Decisions
`logs/<job_id>/secret-decisions.jsonl` (append-only):
```json
{"seq":8,"type":"secret.grant.applied","secret":"BRAVE_API_KEY","tier":"TASK_SECRETS","exposure":"llm_env","policy_sha":"...","ts":"..."}
{"seq":9,"type":"secret.access.attempt","secret":"GH_TOKEN","outcome":"blocked","reason_code":"CONTROL_TIER","ts":"..."}
```

Rules:
- No raw secret values in logs.
- Include deterministic reason codes.
- Include tamper-evident hash chain (`prev_hash`, `hash`).

## Fail-Closed Semantics
- If secret policy missing/unreadable -> fail job before RUNNING.
- If policy hash mismatch -> fail job.
- If grant parser error -> deny all grants.
- If logger unavailable -> block secret-dependent execution.
- If tool asks for undeclared secret -> deny and record.

## Compatibility with PR-Gate Design
| Dimension | Baseline pattern | Secret Boundary v0.1 |
|---|---|---|
| Tiering | Two ad-hoc groups (`SECRETS`, `LLM_SECRETS`) | Formal `CONTROL_SECRETS` + `TASK_SECRETS` |
| Injection method | Shell `eval` export in entrypoint | Structured loader, no eval |
| Exposure control | Prefix naming convention | Per-job explicit grants |
| Auditability | Limited workflow/container logs | Mandatory secret decision ledger |
| Deny defaults | Partial | Global default deny |

Implementation note for baseline migration:
- Keep current source of secrets from workflow, but insert a policy-evaluator sidecar before container start.
- Convert prefix-based classes into explicit grant records for each `job_id`.


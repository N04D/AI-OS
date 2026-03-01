# GitHub Job Branch Runner v0.1

## Purpose
Define a deterministic, auditable, fail-closed execution substrate where each autonomous job is executed on a dedicated Git branch and merged only through policy-enforced PR gating.

## Glossary
| Term | Definition |
|---|---|
| `job_id` | Immutable unique identifier for one requested execution unit. |
| `branch` | Per-job branch, canonical format: `job/<job_id>`. |
| Prompt artifact | Immutable job instruction file stored at `logs/<job_id>/job.md`. |
| PR | Pull request from job branch to protected base branch (typically `main`). |
| Merge gate | Policy evaluator that must return `allow=true` before merge. |
| Ledger | Append-only, ordered job event records with signatures/checksums. |

## Baseline Pattern Observed
Reference implementation snippets:
- `lib/tools/create-job.js:12` -> `const branch = \`job/${jobId}\`;`
- `lib/tools/create-job.js:28` -> `/contents/logs/${jobId}/job.md`
- `templates/.github/workflows/run-job.yml:9` -> `startsWith(github.ref_name, 'job/')`
- `templates/.github/workflows/auto-merge.yml:60` -> `ALLOWED_PATHS="/logs"`

## State Machine
```text
REQUESTED
  -> (approval token validated)
APPROVED
  -> (branch + prompt artifact created atomically)
BRANCHED
  -> (workflow dispatch/create trigger accepted)
RUNNING
  -> (agent commits + opens PR)
PR_OPENED
  -> MERGED    (gate allow + mergeable)
  -> REJECTED  (gate deny / policy violation)
  -> FAILED    (runtime/workflow/system error)
```

### Transition Requirements
| From | To | Preconditions | Evidence |
|---|---|---|---|
| REQUESTED | APPROVED | Valid approval token bound to requester + payload hash | `approval.validated` ledger event |
| APPROVED | BRANCHED | Branch created from approved base SHA; prompt artifact written | `branch.created`, `artifact.written` |
| BRANCHED | RUNNING | Expected workflow run started for `job/<job_id>` | `run.started` with `run_id` |
| RUNNING | PR_OPENED | PR exists with head=`job/<job_id>` | `pr.opened` with `pr_number` |
| PR_OPENED | MERGED/REJECTED/FAILED | Gate verdict or terminal run failure | `gate.verdict` + terminal event |

## Interfaces

## `POST /jobs`
Creates a new job request. Must be fail-closed.

### Request
```json
{
  "job_description": "string",
  "requested_by": "user-or-service-id",
  "base_ref": "main",
  "approval_token": "signed-approval-token",
  "idempotency_key": "uuid"
}
```

### Enforcement
- Reject if `approval_token` missing/invalid/expired.
- Reject if token payload hash != request payload hash.
- Reject if `base_ref` not protected/allowed.
- Must produce the same `job_id` for same idempotency key.

### Response
```json
{
  "job_id": "uuid",
  "branch": "job/<uuid>",
  "state": "BRANCHED",
  "base_sha": "git-sha",
  "artifacts": {
    "prompt": "logs/<job_id>/job.md"
  }
}
```

## `GET /jobs/<id>`
Returns deterministic status projection from ledger + provider state.

### Response
```json
{
  "job_id": "uuid",
  "state": "RUNNING",
  "branch": "job/<uuid>",
  "run_id": 123456,
  "pr_number": 789,
  "base_sha": "...",
  "head_sha": "...",
  "last_event_seq": 14,
  "updated_at": "2026-02-23T16:00:00Z"
}
```

## Signed Webhook Schema
Inbound workflow/result webhooks MUST be signed and replay-protected.

Headers:
- `X-Job-Signature`: `sha256=<hex(hmac)>`
- `X-Job-Timestamp`: unix seconds
- `X-Job-Delivery-Id`: unique id

Body:
```json
{
  "job_id": "uuid",
  "branch": "job/<uuid>",
  "event": "run.completed",
  "status": "success|failure|cancelled|timed_out",
  "run_id": 123,
  "pr_number": 456,
  "head_sha": "...",
  "base_sha": "...",
  "changed_files": ["logs/<job_id>/agent.jsonl"],
  "occurred_at": "2026-02-23T16:00:00Z"
}
```

Validation:
- Reject if signature invalid.
- Reject if timestamp skew exceeds policy window.
- Reject duplicate `delivery_id`.

## Workflow Triggers and Enforcement Guarantees
| Stage | Trigger | Required Guarantee |
|---|---|---|
| Job run | branch create or explicit dispatch for `job/*` | Only `job/<job_id>` branches accepted |
| PR gate | PR opened/synchronized/reopened | Gate evaluates actual diff against policy |
| Merge | gate pass only | Merge blocked on missing/unknown verdict |
| Notify | workflow completion | Notification never mutates merge state |

Notes from baseline:
- `templates/.github/workflows/run-job.yml:4` -> `on: create`
- `templates/.github/workflows/auto-merge.yml:4` -> `on: pull_request`

## Allowed Paths and Merge Gating Contract
- Canonical policy source: repository file (versioned), not mutable runtime variable.
- Gate input: PR diff, policy file at evaluated commit, branch metadata.
- Gate output (deterministic):
```json
{
  "allow": false,
  "reason_code": "PATH_VIOLATION",
  "violations": ["src/server/admin.ts"],
  "policy_sha": "..."
}
```
- Any unknown/indeterminate state MUST deny (`allow=false`).

## Failure Modes (Fail-Closed)
| Failure | Required Behavior |
|---|---|
| Approval validation error | Reject `POST /jobs` |
| Branch create success but artifact write fails | Mark FAILED, prevent execution |
| Missing workflow run | Mark FAILED after bounded timeout |
| Missing gate verdict | Do not merge |
| Signature validation fails | Reject webhook, no state change |
| Ledger write failure | Abort transition; report FAILED |

## Artifacts Produced
Per `job_id`, required paths:
- `logs/<job_id>/job.md` (prompt artifact)
- `logs/<job_id>/events.jsonl` (ordered ledger events)
- `logs/<job_id>/agent.jsonl` (agent session trace)
- `logs/<job_id>/result.json` (terminal normalized result)

`events.jsonl` record shape:
```json
{"seq":1,"job_id":"...","type":"approval.validated","ts":"...","actor":"system","sha256":"..."}
```

## Sequence Flow
```text
Client -> API: POST /jobs + approval_token
API -> GitHub: create refs/heads/job/<job_id>
API -> GitHub: write logs/<job_id>/job.md
GitHub -> Actions: run job workflow
Runner -> Agent Container: execute prompt artifact
Agent Container -> GitHub: push commits, open PR
PR -> PR-Gate: evaluate policy + diff
PR-Gate -> GitHub: required status (pass/fail)
GitHub -> Merge: only on required pass
Actions -> API: signed webhook (terminal state)
```

## Where Patterns Live in Template Repo
- Branch/job creation logic: `lib/tools/create-job.js`
- Job execution workflow: `templates/.github/workflows/run-job.yml`
- Merge policy workflow baseline: `templates/.github/workflows/auto-merge.yml`
- Agent runtime + commit/PR behavior: `templates/docker/job/entrypoint.sh`
- Secret marshaling baseline: `templates/.github/workflows/run-job.yml`

## Compatibility with PR-Gate Design
| Dimension | Baseline (`job/*` + auto-merge checks) | PR-Gate v0.1 Contract |
|---|---|---|
| Branch model | Compatible (`job/<id>`) | Keep as-is |
| Approval control | Prompt/process-level | Enforced API token check |
| Allowlist source | Repo vars (`ALLOWED_PATHS`) | Versioned policy file |
| Merge decision | Workflow shell logic | Deterministic gate verdict artifact |
| Audit trail | Logs + workflow metadata | Append-only ledger with ordered events |
| Failure handling | Mixed best-effort | Explicit fail-closed transition rules |


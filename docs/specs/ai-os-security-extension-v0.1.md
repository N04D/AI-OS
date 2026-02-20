# AI-OS Security Extension v0.2-delta

STATUS: Experimental – Not production-ready – Architectural exploration.
Version: v0.2-delta
Type: Spec + schema tightening only (no runtime implementation)

## 1. Delta Objectives
- Make policy interpretation deterministic (match + precedence + tie-break).
- Bind `review` outcomes to Git-ledgered decision artifacts.
- Remove high-leak secret injection modes by default.
- Prevent userland trust-lift into kernel/supervisor authority.
- Define minimal replay-safe audit event contract.

## 2. Non-goals
- No runtime enforcement implementation.
- No new runtime dependency stack.
- No import of IronClaw runtime architecture.

## 3. Deterministic Rule Evaluation Contract
Policy documents that evaluate rules MUST machine-specify:
- Matching semantics.
- Conflict resolution mode.
- No-match behavior.

Supported conflict modes:
- `deny_wins`
- `most_specific`
- `explicit_priority`

Tie-breaker requirements:
- `tie_breaker: stable_order`
- stable order defined as lexical rule ID order or explicit `order_index`.

Interpretation authority:
- Supervisor is canonical interpretation authority.
- Executor must implement the same contract.
- Any Supervisor/Executor divergence is fail-closed.

## 4. Severity as Machine Contract
Mandatory severity->gating mapping:
- `allow` -> proceed
- `warn` -> proceed + emit audit event
- `block` -> deny + emit audit event
- `review` -> pause execution pending ledgered decision artifact

## 5. Review Ledger Contract
Review decision artifact path:
- `governance/reviews/<review_id>.review.json`

Required fields:
- `review_id`
- `policy_hash`
- `request_fingerprint`
- `decision` (`allow` | `block`)
- `decided_by`
- `timestamp_utc`
- `signature` (or signed commit/tag reference)

Deterministic resume rule:
Execution may resume only when artifact exists in current Git state and both:
- `policy_hash` matches current policy hash
- `request_fingerprint` matches paused request

Any mismatch -> fail-closed and re-review.

## 6. Secrets Boundary Tightening
Default disallowed injection modes:
- `query_param`
- `url_path`

Default allowed modes:
- `header`
- `bearer`
- `body_field` only with `redaction_required: true` and constrained `content_type`

Exception contract for disallowed modes:
- `exception_justification`
- `exception_ttl_seconds`
- `severity_on_use: review`

Secret reference contract must be deterministic and backend-agnostic:
- `secret_ref.provider`: `vault` | `env` | `keychain` | `kms`
- `secret_ref.key`: stable identifier
- `secret_ref.version`: optional stable version

Secret lifetime policy must include one of:
- `expires_at_required: true`
- `rotation_ttl_seconds`

## 7. Network Egress Tightening
- Default fail-closed (`default_effect: deny`).
- Wildcard `*` forbidden.
- `*.example.com` allowed only with `max_subdomain_depth`.
- `path_prefix` must be explicit.

Deterministic DNS/IP handling:
- Use `pinned_ips` or `resolution_snapshot_hash` policy mode.
- Non-replayable resolution context is fail-closed.

Optional structured denylist permitted, but precedence remains deterministic under conflict contract.

## 8. Userland Trust-Lift Prohibition
- Userland integrations are disabled by default unless explicitly policy-granted.
- Userland may not implicitly request kernel/supervisor capability classes.
- Any trust-zone elevation change requires `review` and a ledgered decision artifact.

## 9. Minimal Replay-Safe Audit Event Contract
Canonical event families:
- `policy.evaluated`
- `tool.exec.requested`
- `tool.exec.allowed|blocked|warned|reviewed`
- `net.egress.requested`
- `net.egress.allowed|blocked|warned|reviewed`
- `secret.use.requested`
- `secret.use.allowed|blocked|warned|reviewed`
- `review.paused`
- `review.resolved`

Minimum event fields:
- `event_id`
- `policy_hash`
- ordering integrity via either hash-chain (`prev_event_id`) or deterministic sequence + `stream_hash`

Runtime sink remains implementation-defined, but event format must be stable and replayable.

## 10. Files Hardened by v0.2-delta
- `governance/policy/security/capabilities.schema.json`
- `governance/policy/security/network-egress.schema.json`
- `governance/policy/security/secrets-boundary.schema.json`
- `roadmap/secure-execution-layer.md` (canonical roadmap naming)

## 11. Deferred Implementation
This delta does not implement:
- Executor adapters
- Sandbox runtimes
- MCP runtime guardrail execution
- Event sink backend

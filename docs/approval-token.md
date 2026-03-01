# Approval Token Enforcement (MVP + Supervisor Auto-Signing)

This document defines the server-side approval token required to create a job branch.

## Token Format

`token = base64url(payload_json) + "." + base64url(hmac_sha256(APPROVAL_SECRET, base64url(payload_json)))`

Payload fields:

- `v` (version)
- `issuer` (`human` | `supervisor`)
- `scope` (must include `create_job`)
- `mode` (`auto` | `human_required`)
- `risk_class` (`low` | `medium` | `high`)
- `policy_sha`
- `requested_by`
- `base_ref`
- `payload_sha256`
- `exp` (unix seconds)
- `jti` (UUID)

## Payload Hashing

Server computes deterministic payload hash for incoming request payload using canonical JSON:

- UTF-8 bytes
- object keys sorted
- no whitespace significance

`payload_sha256 = sha256(canonical_json_bytes)` (hex digest)

For `/api/create-job`, payload for hash binding is:

- `body.payload` if present
- otherwise `{ "job": "<job string>" }`

## Capability Policy Source Of Truth

Verifier loads:

- `.gitea/governance/supervisor-capabilities.v1.yaml`
- or `SUPERVISOR_CAPABILITIES_POLICY_PATH` override

The file is JSON-compatible YAML and contains:

- `allowed_scopes`
- `auto_signing_max_risk`
- `lease` (`max_jobs`, `duration_s`, `max_denials`)

If policy file is missing or invalid, verification fails closed.

## Verification Rules (Fail-Closed)

Request is denied unless all checks pass:

1. token present
2. token parses into exactly two dot-separated parts
3. signature matches (constant-time compare)
4. `exp` not expired
5. token schema is exact (unknown/invalid fields denied)
6. `policy_sha` equals hash of loaded capability policy
7. `requested_by` matches request
8. `base_ref` matches request
9. `payload_sha256` matches computed hash
10. `jti` has not been used (replay-protected in sqlite)
11. if issuer is `supervisor`:
    - `SIGNER_SUPERVISOR_ENABLED=true` required
    - `mode=auto` allowed only when `risk_class <= AUTO_SIGNING_MAX_RISK`
    - lease must be active; repeated denials revoke lease

On success, `jti` is persisted with `exp`.

State DB path:

- env `APPROVAL_REPLAY_DB_PATH` (recommended)
- default `/home/infra/night/state/autonomy/approval-replay.sqlite3`

The same sqlite DB stores replay `jti` rows and supervisor lease state.

## Deterministic Risk Classification

Server classifies risk from payload before allowing supervisor auto-signing:

- `low`: only `logs/**` paths requested (or no paths)
- `medium`: any requested path outside `logs/**`
- `high`: requested paths in governance/workflows (for example `governance/**`, `.gitea/governance/**`, `.github/workflows/**`)

If token risk is lower than server-classified risk, deny.

## Decision Matrix (Create Job)

- `issuer=human`: allowed after normal signature/payload/replay/policy checks.
- `issuer=supervisor` + disabled signer: deny.
- `issuer=supervisor` + `mode=human_required`: deny (escalate to human signing).
- `issuer=supervisor` + `mode=auto` + risk above max: deny.
- `issuer=supervisor` + lease revoked/exhausted: deny.

## Deny Reason Codes

- `DENY_TOKEN_MISSING`
- `DENY_TOKEN_BAD_SIG`
- `DENY_TOKEN_EXPIRED`
- `DENY_TOKEN_PAYLOAD_MISMATCH`
- `DENY_TOKEN_REPLAY`
- `DENY_TOKEN_SCHEMA_INVALID`
- `DENY_TOKEN_SUPERVISOR_DISABLED`
- `DENY_TOKEN_HUMAN_REQUIRED`
- `DENY_TOKEN_RISK_TOO_HIGH`
- `DENY_TOKEN_LEASE_REVOKED`
- `DENY_TOKEN_POLICY_MISMATCH`
- `DENY_POLICY_INVALID`
- `DENY_INTERNAL_ERROR`

## Token Minting Helper

Use:

```bash
python scripts/mint_approval_token.py \
  --issuer supervisor \
  --scope create_job \
  --mode auto \
  --risk-class low \
  --requested-by alice \
  --base-ref main \
  --payload-json '{"job":"run nightly checks","requested_paths":["logs/nightly.md"]}' \
  --exp 1893456000 \
  --secret "$APPROVAL_SECRET"
```

The helper prints a token to stdout for testing.

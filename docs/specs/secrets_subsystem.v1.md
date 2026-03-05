# Secrets Subsystem v1

## Goal
Provide a secure, ergonomic, auditable secret storage subsystem for AI-OS with one canonical API (`SecretsManager`) and deterministic fail-closed behavior.

## Threat Model
- Local attacker on same machine: may read files/logs or inspect process command lines.
- Stolen disk / offline analysis: attacker can read user home files and backups.
- Shoulder-surfing: attacker can observe interactive terminal/web UI.
- Compromised process: attacker can call APIs but should not bypass policy/audit path.
- Backups and snapshots: encrypted fallback store may be copied.
- Swap and core dumps: memory remnants may leak runtime plaintext.

## Security Invariants
- I1: plaintext secrets are never written to disk (`keyring` or encrypted fallback only).
- I2: secrets are redacted in logs and object reprs.
- I3: retrieval requires explicit authorization path (policy-aware `get(..., context=...)`).
- I4: fallback store requires user passphrase and modern AEAD (AES-256-GCM) with KDF.
- I5: all operations are auditable without secret material.
- I6: backend absence/uninitialized states fail closed with remediation guidance.

## Out of Scope
- Full prevention of memory scraping in compromised runtime is not possible in Python.
- Mitigations: minimize plaintext lifetime, avoid repr/log emission, best-effort key buffer overwrite, no passphrase persistence.

## Backend Precedence and Policy
- Primary write/read backend: OS keyring (`service=aios`) when available.
- `set`: fallback is used only when keyring unavailable/errors **and** fallback is initialized; operation records explicit notice/audit event.
- `get`: keyring first; fallback lookup allowed only when:
  - keyring unavailable, or
  - key missing in keyring and fallback-search policy allows key/context.
- No initialized backend => explicit fail-closed error.

## Encrypted Fallback Format
- Path: `~/.local/share/aios/secrets/store.v1`
- Versioned binary container:
  - magic bytes + versioned JSON header (`kdf`, `salt`, `nonce`, metadata)
  - AES-256-GCM ciphertext payload (JSON map)
- KDF preference: `scrypt`; fallback `PBKDF2-HMAC-SHA256` (>= 300k iterations; implementation uses 600k).
- AAD binds version + hostname + uid to reduce portability surprises (tradeoff: host/user migration requires managed migration flow).
- Atomic write: temp file + fsync + rename, permissions `0600`.
- Corruption/partial write detection via GCM authentication failure and strict format checks.

## Audit
- Path: `~/.local/share/aios/secrets/audit.jsonl`
- Append-only JSON lines:
  - fields: timestamp, user, action, key, backend, result, error_code
  - no secret material ever logged

## CLI Surface
- `aiosctl secrets status`
- `aiosctl secrets init-fallback`
- `aiosctl secrets set <key> [--from-stdin] [--overwrite]`
- `aiosctl secrets get <key> [--show]`
- `aiosctl secrets delete <key>`
- `aiosctl secrets list [--prefix <p>]`
- `aiosctl secrets rotate-passphrase`
- `aiosctl secrets migrate-to-keyring`

## Web UI Surface
- Route: `/settings/secrets`
- Password-only inputs, no prefill, simple UX text, CSRF token + session, in-memory POST rate limit.

## Test-Backed Guarantees
- Fail-closed behavior when no backend available.
- Fallback encrypt/decrypt round-trip + passphrase rotation.
- Atomic write preservation under replace failure.
- Redaction and audit leak prevention.
- UI save flow does not echo or persist plaintext outside encrypted backend.

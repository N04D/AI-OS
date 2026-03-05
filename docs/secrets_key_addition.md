# Adding Secret Keys Safely

1. Add the new key to policy allowlists intentionally:
- `aios/secrets/policy.py` UI allowlist (`can_ui_edit`) only if non-technical users should manage it.
- Capability allowlist mapping for machine access contexts.

2. Keep canonical naming and validation:
- Use `<domain>.<name>` with `[a-z0-9._-]`.
- Avoid broad or ambiguous names.

3. Access secrets only via `SecretsManager`:
- Never read secret files, env, or side stores directly.
- Pass a `context` for capability-scoped retrieval.

4. Preserve no-leak rules:
- Never log secret values.
- Use `SecretValue` and redaction helpers for any display path.

5. Add/update tests:
- Policy allows/denies as intended.
- CLI/UI paths do not expose plaintext.
- Audit entries include action metadata but no value material.

# Credentials Map (No Secret Values)

Purpose: quick operator reference for where credentials belong and how they are consumed.

## Rules
- Never store secret values in this file.
- Secrets must be retrieved via `SecretsManager` where supported.
- Environment variables are allowed for non-secret config only, unless explicitly temporary.

## Mail transport
- Credential key: `smtp.pass`
- Secret class: password
- Owner: Mail worker
- Source of truth: `SecretsManager`
- Retrieval path: `tools/mail_worker.py` -> `SecretsManager.get(SecretKey("smtp.pass"), context="supervisor.mail_worker.transport")`
- Fallback behavior: fail-closed if secret unavailable

## Mail transport config (non-secret)
- `SMTP_HOST`: SMTP server hostname
- `SMTP_PORT`: SMTP server port (usually `587`)
- `SMTP_USER`: SMTP username/login identity
- `SMTP_FROM`: envelope/header sender
- Storage recommendation: systemd env file or managed runtime config (not in git)

## AI provider
- Credential key: `openai.api_key`
- Source of truth: `SecretsManager`
- UI editable: yes (secrets UI)

## SCM integration
- Credential key: `gitea.token`
- Source of truth: `SecretsManager`
- UI editable: yes (secrets UI)

## GitHub integration
- Credential key: `github.token`
- Source of truth: `SecretsManager`
- Intended use: GitHub API/CLI automation where HTTPS token auth is required
- Storage policy: never in `.env`, git config, or plaintext files

## SSH git access
- Credential type: SSH private key (for example `id_ed25519`)
- Source of truth: operator-managed key file
- Expected location: `~/.ssh/id_ed25519` (private, `0600`) + `~/.ssh/id_ed25519.pub` (public)
- Usage path: `ssh-agent` + Git remote `git@github.com:...`
- Storage policy: private key must never be committed or copied into repo workspace files

## Notes
- Current secrets UI allowlist is curated; add new keys deliberately via policy update.
- For incident review, use audit logs and event artifacts, never plaintext dumps.

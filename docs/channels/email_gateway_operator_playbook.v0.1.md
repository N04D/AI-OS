# Email Gateway Operator Playbook v0.1

Status: ACTIVE  
Scope: Manual operator usage for governed email send/poll flows  
Audience: Maintainers and supervised operators

## 1) Safety Defaults

- Keep `config/channels/email_gateway.json` disabled by default.
- Use `tools/email_safe_run.sh` for all manual runs.
- Never commit secrets.
- Runtime artifacts stay in `runtime/` and logs in `logs/` (ignored).

## 2) Required Environment

Set in local `.env`:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_FROM`

Optional (poll). If omitted, safe-run derives defaults:

- `IMAP_HOST` (defaults to `imap.gmail.com` for Gmail SMTP)
- `IMAP_PORT` (defaults to `993`)
- `IMAP_USER` (defaults to `SMTP_USER`)
- `IMAP_PASS` (defaults to `SMTP_PASS`)

## 3) Safe Send

Allowlisted send:

```bash
./tools/email_safe_run.sh send --json \
  --agent codex \
  --to don.berghuijs@gmail.com \
  --subject "AI-OS Test" \
  --body "Hello from AI-OS"
```

Expected:

- `status: ok`
- outbox artifact created
- audit record with `reason_code: ALLOW`

Blocked send check:

```bash
./tools/email_safe_run.sh send --json \
  --agent codex \
  --to blocked@example.net \
  --subject "Deny check" \
  --body "Should fail"
```

Expected:

- `status: rejected`
- `reason_code: DENY_ADDRESS_NOT_ALLOWED`
- audit deny record written

## 4) Safe Poll

Metadata-only poll (recommended default):

```bash
./tools/email_safe_run.sh poll --json \
  --agent codex \
  --max 50 \
  --seen-mode seen \
  --from-contains "don.berghuijs@gmail.com"
```

Poll with body preview (opt-in only):

```bash
./tools/email_safe_run.sh poll --json \
  --agent codex \
  --max 20 \
  --seen-mode seen \
  --from-contains "don.berghuijs@gmail.com" \
  --include-body-preview \
  --preview-chars 120
```

## 5) Reply Governance

Reply mails (`subject` starts with `Re:`) are governed by:

- `reply_policy.enabled`
- `reply_policy.allowed_senders`
- `reply_policy.require_subject_match`
- `reply_policy.max_replies_per_thread_per_day`

Second reply in same thread/day is denied with:

- `DENY_REPLY_RATE_LIMITED`

Runtime counter:

- `runtime/channels/email_gateway/reply_ledger.json`

## 6) Where To Verify

- Outbox artifacts:
  - `runtime/channels/email_gateway/outbox/codex/`
- Inbox artifacts:
  - `runtime/channels/email_gateway/inbox/codex/`
- Audit log:
  - `logs/control/email_gateway_audit.jsonl`

Quick checks:

```bash
tail -n 5 logs/control/email_gateway_audit.jsonl
ls runtime/channels/email_gateway/outbox/codex | tail
ls runtime/channels/email_gateway/inbox/codex | tail
```

## 7) Incident Handling

If unexpected behavior occurs:

1. Stop manual sends.
2. Rotate SMTP app password.
3. Re-run one deny smoke check.
4. Re-run one allow smoke check.
5. Inspect latest audit lines and reply ledger.

## 8) Operator Rule

Always use `tools/email_safe_run.sh` for manual operations.  
Do not manually keep the module enabled between runs.

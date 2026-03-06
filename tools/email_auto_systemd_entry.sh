#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

AGENT="${AIOS_EMAIL_AGENT:-codex}"
INTERVAL_SECONDS="${AIOS_EMAIL_INTERVAL_SECONDS:-30}"
MAX_MESSAGES="${AIOS_EMAIL_MAX_MESSAGES:-50}"
SEEN_MODE="${AIOS_EMAIL_SEEN_MODE:-unseen}"
FROM_CONTAINS="${AIOS_EMAIL_FROM_CONTAINS:-}"
SUBJECT_CONTAINS="${AIOS_EMAIL_SUBJECT_CONTAINS:-}"
SMTP_HOST="${AIOS_EMAIL_SMTP_HOST:-smtp.gmail.com}"
SMTP_PORT="${AIOS_EMAIL_SMTP_PORT:-587}"
SMTP_USER="${AIOS_EMAIL_SMTP_USER:-}"
SMTP_FROM="${AIOS_EMAIL_SMTP_FROM:-}"
IMAP_HOST="${AIOS_EMAIL_IMAP_HOST:-imap.gmail.com}"
IMAP_PORT="${AIOS_EMAIL_IMAP_PORT:-993}"
IMAP_USER="${AIOS_EMAIL_IMAP_USER:-}"
SMTP_PASS_SECRET_KEY="${AIOS_EMAIL_SMTP_PASS_SECRET_KEY:-smtp.pass}"
KICK_SCRIPT="${AIOS_EMAIL_KICK_SCRIPT:-}"

if [[ -z "$SMTP_USER" ]]; then
  echo "AIOS_EMAIL_SMTP_USER is required" >&2
  exit 2
fi

args=(
  "tools/email_auto_loop.py"
  "--agent" "$AGENT"
  "--interval-seconds" "$INTERVAL_SECONDS"
  "--max-messages" "$MAX_MESSAGES"
  "--seen-mode" "$SEEN_MODE"
  "--smtp-host" "$SMTP_HOST"
  "--smtp-port" "$SMTP_PORT"
  "--smtp-user" "$SMTP_USER"
  "--imap-host" "$IMAP_HOST"
  "--imap-port" "$IMAP_PORT"
  "--smtp-pass-secret-key" "$SMTP_PASS_SECRET_KEY"
)

if [[ -n "$SMTP_FROM" ]]; then
  args+=("--smtp-from" "$SMTP_FROM")
fi
if [[ -n "$IMAP_USER" ]]; then
  args+=("--imap-user" "$IMAP_USER")
fi
if [[ -n "$FROM_CONTAINS" ]]; then
  args+=("--from-contains" "$FROM_CONTAINS")
fi
if [[ -n "$SUBJECT_CONTAINS" ]]; then
  args+=("--subject-contains" "$SUBJECT_CONTAINS")
fi
if [[ -n "$KICK_SCRIPT" ]]; then
  args+=("--kick-script" "$KICK_SCRIPT")
fi

exec .venv/bin/python "${args[@]}"

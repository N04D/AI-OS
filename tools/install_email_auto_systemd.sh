#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  tools/install_email_auto_systemd.sh install --smtp-user <email> [options]
  tools/install_email_auto_systemd.sh uninstall
  tools/install_email_auto_systemd.sh status

Options for install:
  --smtp-user <email>                Required
  --smtp-from <email>                Default: smtp-user
  --agent <name>                     Default: codex
  --interval-seconds <int>           Default: 30
  --max-messages <int>               Default: 50
  --seen-mode <mode>                 unseen|seen|all (default: unseen)
  --from-contains <text>             Optional IMAP filter
  --subject-contains <text>          Optional IMAP filter
  --smtp-host <host>                 Default: smtp.gmail.com
  --smtp-port <port>                 Default: 587
  --imap-host <host>                 Default: imap.gmail.com
  --imap-port <port>                 Default: 993
  --imap-user <email>                Optional (defaults to smtp-user)
  --smtp-pass-secret-key <key>       Default: smtp.pass

Examples:
  tools/install_email_auto_systemd.sh install --smtp-user nova69.agent@gmail.com --smtp-from nova69.agent@gmail.com
  tools/install_email_auto_systemd.sh status
  tools/install_email_auto_systemd.sh uninstall
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

ACTION="$1"
shift

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "error: run this script inside the repository" >&2
  exit 2
fi
cd "$REPO_ROOT"

UNIT_NAME="aios-email-auto.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
ENV_DIR="$HOME/.config/aios"
ENV_FILE="$ENV_DIR/email_auto.env"
UNIT_FILE="$SYSTEMD_USER_DIR/$UNIT_NAME"

AGENT="codex"
SMTP_USER=""
SMTP_FROM=""
INTERVAL_SECONDS="30"
MAX_MESSAGES="50"
SEEN_MODE="unseen"
FROM_CONTAINS=""
SUBJECT_CONTAINS=""
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
IMAP_HOST="imap.gmail.com"
IMAP_PORT="993"
IMAP_USER=""
SMTP_PASS_SECRET_KEY="smtp.pass"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smtp-user) SMTP_USER="${2:-}"; shift 2 ;;
    --smtp-from) SMTP_FROM="${2:-}"; shift 2 ;;
    --agent) AGENT="${2:-}"; shift 2 ;;
    --interval-seconds) INTERVAL_SECONDS="${2:-}"; shift 2 ;;
    --max-messages) MAX_MESSAGES="${2:-}"; shift 2 ;;
    --seen-mode) SEEN_MODE="${2:-}"; shift 2 ;;
    --from-contains) FROM_CONTAINS="${2:-}"; shift 2 ;;
    --subject-contains) SUBJECT_CONTAINS="${2:-}"; shift 2 ;;
    --smtp-host) SMTP_HOST="${2:-}"; shift 2 ;;
    --smtp-port) SMTP_PORT="${2:-}"; shift 2 ;;
    --imap-host) IMAP_HOST="${2:-}"; shift 2 ;;
    --imap-port) IMAP_PORT="${2:-}"; shift 2 ;;
    --imap-user) IMAP_USER="${2:-}"; shift 2 ;;
    --smtp-pass-secret-key) SMTP_PASS_SECRET_KEY="${2:-}"; shift 2 ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

install_unit() {
  if [[ -z "$SMTP_USER" ]]; then
    echo "error: --smtp-user is required for install" >&2
    exit 2
  fi
  if [[ -z "$SMTP_FROM" ]]; then
    SMTP_FROM="$SMTP_USER"
  fi
  mkdir -p "$SYSTEMD_USER_DIR" "$ENV_DIR"
  cat >"$ENV_FILE" <<EOF
AIOS_EMAIL_AGENT=$AGENT
AIOS_EMAIL_INTERVAL_SECONDS=$INTERVAL_SECONDS
AIOS_EMAIL_MAX_MESSAGES=$MAX_MESSAGES
AIOS_EMAIL_SEEN_MODE=$SEEN_MODE
AIOS_EMAIL_FROM_CONTAINS=$FROM_CONTAINS
AIOS_EMAIL_SUBJECT_CONTAINS=$SUBJECT_CONTAINS
AIOS_EMAIL_SMTP_HOST=$SMTP_HOST
AIOS_EMAIL_SMTP_PORT=$SMTP_PORT
AIOS_EMAIL_SMTP_USER=$SMTP_USER
AIOS_EMAIL_SMTP_FROM=$SMTP_FROM
AIOS_EMAIL_IMAP_HOST=$IMAP_HOST
AIOS_EMAIL_IMAP_PORT=$IMAP_PORT
AIOS_EMAIL_IMAP_USER=$IMAP_USER
AIOS_EMAIL_SMTP_PASS_SECRET_KEY=$SMTP_PASS_SECRET_KEY
EOF
  chmod 600 "$ENV_FILE"

  cat >"$UNIT_FILE" <<EOF
[Unit]
Description=AI-OS Email Auto Loop
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$REPO_ROOT
EnvironmentFile=$ENV_FILE
ExecStart=$REPO_ROOT/tools/email_auto_systemd_entry.sh
Restart=always
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now "$UNIT_NAME"
  echo "installed and started: $UNIT_NAME"
  systemctl --user status "$UNIT_NAME" --no-pager || true
}

uninstall_unit() {
  systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
  rm -f "$UNIT_FILE"
  systemctl --user daemon-reload
  echo "removed: $UNIT_FILE"
  echo "kept env file: $ENV_FILE"
}

status_unit() {
  if [[ -f "$UNIT_FILE" ]]; then
    echo "unit file: $UNIT_FILE"
  else
    echo "unit file not found: $UNIT_FILE"
  fi
  if [[ -f "$ENV_FILE" ]]; then
    echo "env file: $ENV_FILE"
  else
    echo "env file not found: $ENV_FILE"
  fi
  systemctl --user status "$UNIT_NAME" --no-pager || true
}

case "$ACTION" in
  install) install_unit ;;
  uninstall) uninstall_unit ;;
  status) status_unit ;;
  *)
    echo "error: action must be install|uninstall|status" >&2
    usage
    exit 2
    ;;
esac

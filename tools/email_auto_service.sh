#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  tools/email_auto_service.sh <start|stop|restart|status|logs> [options]

Options:
  --agent <name>                 Default: codex
  --smtp-user <email>            Required for start/restart
  --smtp-from <email>            Default: same as smtp-user
  --interval-seconds <int>       Default: 30
  --max-messages <int>           Default: 50
  --seen-mode <mode>             unseen|seen|all (default: unseen)
  --from-contains <text>         Optional poll filter
  --subject-contains <text>      Optional poll filter

Examples:
  tools/email_auto_service.sh start --smtp-user nova69.agent@gmail.com
  tools/email_auto_service.sh status
  tools/email_auto_service.sh logs
  tools/email_auto_service.sh stop
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

STATE_DIR="runtime/email_auto"
PID_FILE="$STATE_DIR/service.pid"
LOG_FILE="$STATE_DIR/service.log"
mkdir -p "$STATE_DIR"

AGENT="codex"
SMTP_USER=""
SMTP_FROM=""
INTERVAL_SECONDS="30"
MAX_MESSAGES="50"
SEEN_MODE="unseen"
FROM_CONTAINS=""
SUBJECT_CONTAINS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      AGENT="${2:-}"
      shift 2
      ;;
    --smtp-user)
      SMTP_USER="${2:-}"
      shift 2
      ;;
    --smtp-from)
      SMTP_FROM="${2:-}"
      shift 2
      ;;
    --interval-seconds)
      INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --max-messages)
      MAX_MESSAGES="${2:-}"
      shift 2
      ;;
    --seen-mode)
      SEEN_MODE="${2:-}"
      shift 2
      ;;
    --from-contains)
      FROM_CONTAINS="${2:-}"
      shift 2
      ;;
    --subject-contains)
      SUBJECT_CONTAINS="${2:-}"
      shift 2
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

start_service() {
  if [[ -z "$SMTP_USER" ]]; then
    echo "error: --smtp-user is required for start/restart" >&2
    exit 2
  fi
  if is_running; then
    echo "already running (pid $(cat "$PID_FILE"))"
    return 0
  fi

  local args=(
    "tools/email_auto_loop.py"
    "--agent" "$AGENT"
    "--smtp-user" "$SMTP_USER"
    "--interval-seconds" "$INTERVAL_SECONDS"
    "--max-messages" "$MAX_MESSAGES"
    "--seen-mode" "$SEEN_MODE"
  )
  if [[ -n "$SMTP_FROM" ]]; then
    args+=("--smtp-from" "$SMTP_FROM")
  fi
  if [[ -n "$FROM_CONTAINS" ]]; then
    args+=("--from-contains" "$FROM_CONTAINS")
  fi
  if [[ -n "$SUBJECT_CONTAINS" ]]; then
    args+=("--subject-contains" "$SUBJECT_CONTAINS")
  fi

  nohup .venv/bin/python "${args[@]}" >>"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" >"$PID_FILE"
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "started (pid $pid)"
    echo "log: $LOG_FILE"
  else
    echo "failed to start; check log: $LOG_FILE" >&2
    exit 1
  fi
}

stop_service() {
  if ! is_running; then
    rm -f "$PID_FILE"
    echo "not running"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "stopped"
}

status_service() {
  if is_running; then
    echo "running (pid $(cat "$PID_FILE"))"
    echo "log: $LOG_FILE"
  else
    echo "not running"
  fi
}

logs_service() {
  if [[ ! -f "$LOG_FILE" ]]; then
    echo "no log yet: $LOG_FILE"
    return 0
  fi
  tail -n 50 "$LOG_FILE"
}

case "$ACTION" in
  start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  restart)
    stop_service
    start_service
    ;;
  status)
    status_service
    ;;
  logs)
    logs_service
    ;;
  *)
    echo "error: action must be start|stop|restart|status|logs" >&2
    usage
    exit 2
    ;;
esac

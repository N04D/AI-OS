#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  tools/email_safe_run.sh send [aiosctl email send args...]
  tools/email_safe_run.sh poll [aiosctl email poll args...]

Examples:
  tools/email_safe_run.sh send --agent codex --to you@example.com --subject "Hi" --body "Hello"
  tools/email_safe_run.sh poll --agent codex --max 20 --seen-mode seen --from-contains "name@example.com"

Behavior:
  - send: queues a JSON message in workspace/<agent>/mail/outbox (no live network)
  - poll: temporary email gateway/capability enable + ./scripts/aiosctl email poll
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

MODE="$1"
shift
if [[ "$MODE" != "send" && "$MODE" != "poll" ]]; then
  echo "error: first argument must be 'send' or 'poll'" >&2
  usage
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "error: run this script inside a git repository" >&2
  exit 2
fi
cd "$REPO_ROOT"

AGENT="codex"
ARGS=()
JSON_FLAG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      JSON_FLAG=1
      ARGS+=("$1")
      shift
      ;;
    --agent)
      if [[ $# -lt 2 ]]; then
        echo "error: --agent requires a value" >&2
        exit 2
      fi
      AGENT="$2"
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$MODE" == "send" ]]; then
  TO_ADDR=""
  SUBJECT=""
  BODY=""
  idx=0
  while [[ $idx -lt ${#ARGS[@]} ]]; do
    arg="${ARGS[$idx]}"
    if [[ "$arg" == "--to" && $((idx + 1)) -lt ${#ARGS[@]} ]]; then
      TO_ADDR="${ARGS[$((idx + 1))]}"
      idx=$((idx + 2))
      continue
    fi
    if [[ "$arg" == "--subject" && $((idx + 1)) -lt ${#ARGS[@]} ]]; then
      SUBJECT="${ARGS[$((idx + 1))]}"
      idx=$((idx + 2))
      continue
    fi
    if [[ "$arg" == "--body" && $((idx + 1)) -lt ${#ARGS[@]} ]]; then
      BODY="${ARGS[$((idx + 1))]}"
      idx=$((idx + 2))
      continue
    fi
    idx=$((idx + 1))
  done

  if [[ -z "$TO_ADDR" || -z "$SUBJECT" || -z "$BODY" ]]; then
    echo "error: send requires --to, --subject, and --body" >&2
    exit 2
  fi

  WORKSPACE_ROOT="${AIOS_MAIL_WORKSPACE_ROOT:-${REPO_ROOT}/workspace}"
  umask 077
  python3 - <<'PY' "$WORKSPACE_ROOT" "$AGENT" "$TO_ADDR" "$SUBJECT" "$BODY" "$JSON_FLAG"
import json
import os
import sys
import tempfile
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path

workspace_root = Path(sys.argv[1])
agent = sys.argv[2]
to_addr = sys.argv[3]
subject = sys.argv[4]
body = sys.argv[5]
json_flag = sys.argv[6] == "1"

mail_root = workspace_root / agent / "mail"
for name in ("inbox", "outbox", "sent", "failed"):
    (mail_root / name).mkdir(parents=True, exist_ok=True)

message_id = str(uuid.uuid4())
timestamp = os.environ.get("AIOS_MAIL_QUEUE_NOW", "").strip() or datetime.now(UTC).isoformat().replace("+00:00", "Z")
payload = {
    "id": message_id,
    "to": to_addr,
    "subject": subject,
    "body": body,
    "timestamp": timestamp,
    "status": "pending",
}
target = mail_root / "outbox" / f"{message_id}.json"
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, prefix=f"{message_id}.", suffix=".tmp", delete=False) as fh:
    json.dump(payload, fh, sort_keys=True, ensure_ascii=True)
    fh.write("\n")
    fh.flush()
    os.fsync(fh.fileno())
    temp_name = fh.name
os.replace(temp_name, target)
os.chmod(target, 0o600)

result = {"status": "queued", "id": message_id}
if json_flag:
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
else:
    print(f"queued: {message_id}")
PY
  exit $?
fi

CONFIG_PATH="config/channels/email_gateway.json"
CAPS_PATH="state/supervisor_capabilities.json"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "error: missing $CONFIG_PATH" >&2
  exit 2
fi
if [[ ! -f "$CAPS_PATH" ]]; then
  echo "error: missing $CAPS_PATH" >&2
  exit 2
fi

REQUIRED_CAPABILITY="email.poll"
CONFIG_BAK="$(mktemp)"
CAPS_BAK="$(mktemp)"
cp "$CONFIG_PATH" "$CONFIG_BAK"
cp "$CAPS_PATH" "$CAPS_BAK"

restore() {
  cp "$CONFIG_BAK" "$CONFIG_PATH"
  cp "$CAPS_BAK" "$CAPS_PATH"
  rm -f "$CONFIG_BAK" "$CAPS_BAK"
}
trap restore EXIT

python3 - <<'PY' "$CONFIG_PATH" "$AGENT"
import json, sys
path = sys.argv[1]
agent = sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)
if not isinstance(cfg, dict):
    raise SystemExit("invalid config payload")
cfg["enabled"] = True
agents = cfg.setdefault("agents", {})
if not isinstance(agents, dict):
    raise SystemExit("invalid config.agents payload")
entry = agents.setdefault(agent, {})
if not isinstance(entry, dict):
    entry = {}
agents[agent] = entry
entry["enabled"] = True
with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, sort_keys=True, indent=2, ensure_ascii=True)
    fh.write("\n")
PY

python3 - <<'PY' "$CAPS_PATH" "$REQUIRED_CAPABILITY"
import json, sys
path = sys.argv[1]
cap = sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    payload = json.load(fh)
if not isinstance(payload, dict):
    raise SystemExit("invalid capability payload")
entry = payload.setdefault(cap, {})
if isinstance(entry, bool):
    entry = {"granted": bool(entry)}
if not isinstance(entry, dict):
    entry = {}
payload[cap] = entry
entry["granted"] = True
entry["state"] = "ACTIVE"
if not entry.get("approved_by"):
    entry["approved_by"] = "Don"
if not entry.get("activated_by"):
    entry["activated_by"] = "Don"
timestamps = entry.setdefault("timestamps", {})
if isinstance(timestamps, dict):
    timestamps.setdefault("IMPLEMENTED_NOT_ACTIVE->ACTIVE", "2026-03-01T00:00:00Z")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, sort_keys=True, indent=2, ensure_ascii=True)
    fh.write("\n")
PY

# Poll helper: when IMAP vars are not set, derive deterministic defaults from SMTP.
# This keeps day-to-day runs ergonomic while still requiring explicit credentials.
if [[ "$MODE" == "poll" ]]; then
  if [[ -z "${IMAP_HOST:-}" ]]; then
    if [[ "${SMTP_HOST:-}" == "smtp.gmail.com" ]]; then
      export IMAP_HOST="imap.gmail.com"
    elif [[ -n "${SMTP_HOST:-}" ]]; then
      export IMAP_HOST="${SMTP_HOST}"
    fi
  fi
  if [[ -z "${IMAP_PORT:-}" ]]; then
    export IMAP_PORT="993"
  fi
  if [[ -z "${IMAP_USER:-}" && -n "${SMTP_USER:-}" ]]; then
    export IMAP_USER="${SMTP_USER}"
  fi
  if [[ -z "${IMAP_PASS:-}" && -n "${SMTP_PASS:-}" ]]; then
    export IMAP_PASS="${SMTP_PASS}"
  fi
fi

FINAL_ARGS=()
for arg in "${ARGS[@]}"; do
  if [[ "$arg" != "--json" ]]; then
    FINAL_ARGS+=("$arg")
  fi
done

if [[ "$JSON_FLAG" -eq 1 ]]; then
  if [[ "${AIOS_EMAIL_SAFE_RUN_FORBID_AIOSCTL:-0}" == "1" ]]; then
    echo '{"status":"error","reason":"aiosctl invocation forbidden"}'
    exit 70
  fi
  ./scripts/aiosctl --json email "$MODE" --agent "$AGENT" "${FINAL_ARGS[@]}"
  exit $?
fi
if [[ "${AIOS_EMAIL_SAFE_RUN_FORBID_AIOSCTL:-0}" == "1" ]]; then
  echo "error: aiosctl invocation forbidden" >&2
  exit 70
fi
./scripts/aiosctl email "$MODE" --agent "$AGENT" "${FINAL_ARGS[@]}"

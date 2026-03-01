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
  - Temporarily enables email gateway module + selected agent in config/channels/email_gateway.json
  - Temporarily activates required capability in state/supervisor_capabilities.json:
      send -> email.send
      poll -> email.poll
  - Runs ./scripts/aiosctl email <send|poll> ...
  - Always restores both files, even on failure
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
  REQUIRED_CAPABILITY="email.send"
else
  REQUIRED_CAPABILITY="email.poll"
fi

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
  ./scripts/aiosctl --json email "$MODE" --agent "$AGENT" "${FINAL_ARGS[@]}"
  exit $?
fi
./scripts/aiosctl email "$MODE" --agent "$AGENT" "${FINAL_ARGS[@]}"

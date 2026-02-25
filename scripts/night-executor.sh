#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: python3/python not found" >&2
  exit 22
fi

if [ -z "${GITEA_TOKEN:-}" ]; then
  if [ -f /home/infra/.secrets/gitea_token ]; then
    export GITEA_TOKEN="$(cat /home/infra/.secrets/gitea_token)"
  else
    echo "ERROR: GITEA_TOKEN not set and no secret file found at /home/infra/.secrets/gitea_token" >&2
    exit 1
  fi
fi

if [ -z "${GITEA_BASE_URL:-}" ]; then
  if [ -f /home/infra/.secrets/gitea_base_url ]; then
    export GITEA_BASE_URL="$(cat /home/infra/.secrets/gitea_base_url)"
  fi
fi

if [ -z "${GITEA_BASE_URL:-}" ]; then
  echo "ERROR: GITEA_BASE_URL not set" >&2
  exit 1
fi

HOST_STATE_DIR="${HOST_STATE_DIR:-/home/infra/night/state}"
LEDGER_DIR="${LEDGER_DIR:-$HOST_STATE_DIR/ledger}"
mkdir -p "$LEDGER_DIR"
export LEDGER_DIR

QUEUE_PATH="${1:-governance/night-queue.yaml}"
"$PYTHON_BIN" -m supervisor.night_executor --queue "${QUEUE_PATH}" --ledger-dir "${LEDGER_DIR}"

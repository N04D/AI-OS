#!/usr/bin/env bash
set -euo pipefail

if [ -z "${GITEA_TOKEN:-}" ]; then
  if [ -f /home/infra/.secrets/gitea_token ]; then
    export GITEA_TOKEN="$(cat /home/infra/.secrets/gitea_token)"
  else
    echo "ERROR: GITEA_TOKEN not set and no secret file found at /home/infra/.secrets/gitea_token" >&2
    exit 1
  fi
fi

if [ -z "${GITEA_BASE_URL:-}" ]; then
  echo "ERROR: GITEA_BASE_URL not set" >&2
  exit 1
fi

QUEUE_PATH="${1:-governance/night-queue.yaml}"
python -m supervisor.night_executor --queue "${QUEUE_PATH}"

#!/usr/bin/env bash
set -euo pipefail
KEY="/data/srv/aios/AI-OS/workspace/codex/.ssh/ai-os-codex-agent.2026-03-03.private-key.pem"
exec ssh -i "$KEY" -o IdentitiesOnly=yes "$@"

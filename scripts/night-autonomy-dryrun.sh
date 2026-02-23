#!/usr/bin/env bash
set -euo pipefail

TMP_QUEUE="$(mktemp)"
HAD_PROPOSALS_DIR=0
if [ -d "docs/autonomy/proposals" ]; then
  HAD_PROPOSALS_DIR=1
fi
cleanup() {
  rm -f "$TMP_QUEUE"
  if [ "$HAD_PROPOSALS_DIR" -eq 0 ] && [ -d "docs/autonomy/proposals" ]; then
    rm -rf "docs/autonomy/proposals"
    rmdir "docs/autonomy" 2>/dev/null || true
    rmdir "docs" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cat > "$TMP_QUEUE" <<'YAML'
mode: night-autonomy-dryrun-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
YAML

set +e
./scripts/night-executor.sh "$TMP_QUEUE"
CODE=$?
set -e

exit "$CODE"

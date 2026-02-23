#!/usr/bin/env bash
set -euo pipefail

TMP_QUEUE="$(mktemp)"
cleanup() {
  rm -f "$TMP_QUEUE"
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

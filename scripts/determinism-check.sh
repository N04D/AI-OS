#!/usr/bin/env bash
set -euo pipefail

# Exit code contract (deterministic):
#   0  success
#  20  git_untrusted
#  21  git_dirty
#  22  runner_missing

EXIT_OK=0
EXIT_GIT_UNTRUSTED=20
EXIT_GIT_DIRTY=21
EXIT_RUNNER_MISSING=22

echo "Checking git trust..."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Git trust/repository check failed"
  exit "$EXIT_GIT_UNTRUSTED"
fi

echo "Checking for uncommitted changes..."
if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes detected"
  exit "$EXIT_GIT_DIRTY"
fi

echo "Checking deterministic harness prerequisites..."
if [ ! -f "./scripts/test-all.sh" ]; then
  echo "Missing canonical harness ./scripts/test-all.sh"
  exit "$EXIT_RUNNER_MISSING"
fi

exit "$EXIT_OK"

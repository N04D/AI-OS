#!/usr/bin/env bash
set -euo pipefail

echo "Checking for uncommitted changes..."
if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes detected"
  exit 1
fi

echo "Checking deterministic harness prerequisites..."
if [ ! -f "./scripts/test-all.sh" ]; then
  echo "Missing canonical harness ./scripts/test-all.sh"
  exit 1
fi

exit 0

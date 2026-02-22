#!/usr/bin/env bash
set -euo pipefail

NIGHT_DIR="${NIGHT_DIR:-/home/infra/night/AI-OS}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGIN_URL="$(git -C "$REPO_ROOT" config --get remote.origin.url)"

if [ -z "$ORIGIN_URL" ]; then
  echo "ERROR: missing remote.origin.url" >&2
  exit 1
fi

if [ ! -d "$NIGHT_DIR/.git" ]; then
  mkdir -p "$(dirname "$NIGHT_DIR")"
  git clone "$ORIGIN_URL" "$NIGHT_DIR"
fi

cd "$NIGHT_DIR"
git fetch --all
git checkout main
git reset --hard origin/main
git clean -fd

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: night workspace is dirty" >&2
  exit 1
fi

./scripts/test-all.sh

echo "NIGHT_WORKSPACE_READY=1"
echo "NIGHT_WORKSPACE_PATH=$NIGHT_DIR"

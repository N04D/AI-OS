#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NIGHT_DIR="${NIGHT_DIR:-$REPO_ROOT/.night/AI-OS}"
NIGHT_BRANCH="${NIGHT_BRANCH:-dev}"
if git -C "$REPO_ROOT" remote get-url gitea >/dev/null 2>&1; then
  SELECTED_REMOTE="gitea"
  REMOTE_URL="$(git -C "$REPO_ROOT" remote get-url gitea)"
else
  SELECTED_REMOTE="origin"
  REMOTE_URL="$(git -C "$REPO_ROOT" config --get remote.origin.url)"
fi

if [ -z "$REMOTE_URL" ]; then
  echo "ERROR: missing remote.$SELECTED_REMOTE.url" >&2
  exit 1
fi

echo "NIGHT_BOOTSTRAP_SELECTED_REMOTE=$SELECTED_REMOTE"
echo "NIGHT_BOOTSTRAP_SOURCE_REMOTE_URL=$REMOTE_URL"
echo "NIGHT_BOOTSTRAP_TARGET_DIR=$NIGHT_DIR"

if [ ! -d "$NIGHT_DIR/.git" ]; then
  mkdir -p "$(dirname "$NIGHT_DIR")"
  git clone "$REMOTE_URL" "$NIGHT_DIR"
fi

cd "$NIGHT_DIR"
git remote set-url origin "$REMOTE_URL"
git fetch --prune --all

if ! git show-ref --verify --quiet "refs/remotes/origin/$NIGHT_BRANCH"; then
  echo "ERROR: target branch does not exist on selected remote ($SELECTED_REMOTE): $NIGHT_BRANCH" >&2
  exit 1
fi

echo "NIGHT_BOOTSTRAP_TARGET_BRANCH=$NIGHT_BRANCH"
git checkout "$NIGHT_BRANCH"
git reset --hard "origin/$NIGHT_BRANCH"
git clean -fd

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: night workspace is dirty" >&2
  exit 1
fi

if [ -f ./scripts/test-all.sh ]; then
  HARNESS="./scripts/test-all.sh"
elif [ -f ./script/test-all.sh ]; then
  HARNESS="./script/test-all.sh"
else
  echo "ERROR: missing test harness (expected ./scripts/test-all.sh or ./script/test-all.sh)" >&2
  echo "DEBUG: git log -1" >&2
  git log -1 --oneline >&2 || true
  echo "DEBUG: current branch" >&2
  git branch --show-current >&2 || true
  echo "DEBUG: remote -v" >&2
  git remote -v >&2 || true
  echo "DEBUG: repo root listing" >&2
  ls -la >&2 || true
  exit 1
fi

echo "NIGHT_BOOTSTRAP_HARNESS=$HARNESS"
"$HARNESS"

echo "NIGHT_WORKSPACE_READY=1"
echo "NIGHT_WORKSPACE_PATH=$NIGHT_DIR"

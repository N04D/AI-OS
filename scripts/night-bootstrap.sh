#!/usr/bin/env bash
set -euo pipefail

NIGHT_DIR="${NIGHT_DIR:-/home/infra/night/AI-OS}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if git -C "$REPO_ROOT" remote get-url gitea >/dev/null 2>&1; then
  SELECTED_REMOTE="gitea"
  ORIGIN_URL="$(git -C "$REPO_ROOT" remote get-url gitea)"
else
  SELECTED_REMOTE="origin"
  ORIGIN_URL="$(git -C "$REPO_ROOT" config --get remote.origin.url)"
fi

if [ -z "$ORIGIN_URL" ]; then
  echo "ERROR: missing remote.origin.url" >&2
  exit 1
fi

echo "NIGHT_BOOTSTRAP_SELECTED_REMOTE=$SELECTED_REMOTE"
echo "NIGHT_BOOTSTRAP_SOURCE_ORIGIN=$ORIGIN_URL"
echo "NIGHT_BOOTSTRAP_TARGET_DIR=$NIGHT_DIR"

if [ ! -d "$NIGHT_DIR/.git" ]; then
  mkdir -p "$(dirname "$NIGHT_DIR")"
  git clone "$ORIGIN_URL" "$NIGHT_DIR"
fi

cd "$NIGHT_DIR"
git remote set-url origin "$ORIGIN_URL"
git fetch --prune --all

DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD | sed 's@^origin/@@')"
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="$(git remote show origin | sed -n '/HEAD branch/s/.*: //p' | head -n1)"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: could not determine default branch from origin/HEAD" >&2
  exit 1
fi

echo "NIGHT_BOOTSTRAP_DEFAULT_BRANCH=$DEFAULT_BRANCH"
git checkout "$DEFAULT_BRANCH"
git reset --hard "origin/$DEFAULT_BRANCH"
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

#!/usr/bin/env bash
set -euo pipefail

# ============================================
# AI-OS Canonical Test Harness v0.1
# Exit code contract (deterministic):
#   0  success
#  20  git_untrusted
#  21  git_dirty
#  22  runner_missing
#  23  tests_failed
# ============================================

EXIT_OK=0
EXIT_GIT_UNTRUSTED=20
EXIT_GIT_DIRTY=21
EXIT_RUNNER_MISSING=22
EXIT_TESTS_FAILED=23

START_TS=$(date +%s%3N)

echo "=== AI-OS TEST HARNESS START ==="
echo "Timestamp: $START_TS"

FAIL=0
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

# --------------------------------------------
# 0. Working Tree Must Be Clean (fail-closed)
# --------------------------------------------

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[precheck] FAILED (git_untrusted)"
  echo "=== TEST HARNESS FAILED ==="
  exit "$EXIT_GIT_UNTRUSTED"
fi

if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "[precheck] FAILED (working tree dirty)"
  echo "=== TEST HARNESS FAILED ==="
  exit "$EXIT_GIT_DIRTY"
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "[precheck] FAILED (runner_missing: python3/python unavailable)"
  echo "=== TEST HARNESS FAILED ==="
  exit "$EXIT_RUNNER_MISSING"
fi

# --------------------------------------------
# 1. Lint / Static Checks
# --------------------------------------------

if [ -f "./scripts/lint.sh" ]; then
  echo "[lint] running..."
  if ! ./scripts/lint.sh; then
    echo "[lint] FAILED"
    FAIL=1
  else
    echo "[lint] OK"
  fi
else
  echo "[lint] skipped (no lint.sh)"
fi

# --------------------------------------------
# 2. Unit Tests
# --------------------------------------------

if "$PYTHON_BIN" -c "import pytest" >/dev/null 2>&1; then
  echo "[tests] running pytest..."
  if ! "$PYTHON_BIN" -m pytest -q; then
    echo "[tests] FAILED"
    FAIL=1
  else
    echo "[tests] OK"
  fi
else
  echo "[tests] pytest unavailable, running unittest fallback..."
  if ! "$PYTHON_BIN" -m unittest discover -s supervisor/tests -p "test_*.py"; then
    echo "[tests] FAILED"
    FAIL=1
  else
    echo "[tests] OK"
  fi

  if ! "$PYTHON_BIN" -m unittest discover -s tests -p "test_*.py"; then
    echo "[tests-root] FAILED"
    FAIL=1
  else
    echo "[tests-root] OK"
  fi
fi

# --------------------------------------------
# 3. Type Checks (optional)
# --------------------------------------------

if "$PYTHON_BIN" -m mypy --version >/dev/null 2>&1 && { [ -f "mypy.ini" ] || [ -f "pyproject.toml" ] || [ -f "setup.cfg" ]; }; then
  echo "[typecheck] running mypy..."
  if ! "$PYTHON_BIN" -m mypy .; then
    echo "[typecheck] FAILED"
    FAIL=1
  else
    echo "[typecheck] OK"
  fi
else
  if ! "$PYTHON_BIN" -m mypy --version >/dev/null 2>&1; then
    echo "[typecheck] skipped (no mypy)"
  else
    echo "[typecheck] skipped (no mypy config)"
  fi
fi

# --------------------------------------------
# 4. Determinism Gate (required, fail-closed)
# --------------------------------------------

if [ ! -f "./scripts/determinism-check.sh" ]; then
  echo "[determinism] FAILED (runner_missing: missing ./scripts/determinism-check.sh)"
  echo "=== TEST HARNESS FAILED ==="
  exit "$EXIT_RUNNER_MISSING"
else
  echo "[determinism] running..."
  if [ -x "./scripts/determinism-check.sh" ]; then
    if ! ./scripts/determinism-check.sh; then
      echo "[determinism] FAILED"
      FAIL=1
    else
      echo "[determinism] OK"
    fi
  else
    if ! bash ./scripts/determinism-check.sh; then
      echo "[determinism] FAILED"
      FAIL=1
    else
      echo "[determinism] OK"
    fi
  fi
fi

# --------------------------------------------
# Final
# --------------------------------------------

END_TS=$(date +%s%3N)
DURATION=$((END_TS - START_TS))

echo "Duration: ${DURATION} ms"

if [ "$FAIL" -ne 0 ]; then
  echo "=== TEST HARNESS FAILED ==="
  exit "$EXIT_TESTS_FAILED"
fi

echo "=== TEST HARNESS PASSED ==="
exit "$EXIT_OK"

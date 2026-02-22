#!/usr/bin/env bash
set -euo pipefail

# ============================================
# AI-OS Canonical Test Harness v0.1
# ============================================

START_TS=$(date +%s%3N)

echo "=== AI-OS TEST HARNESS START ==="
echo "Timestamp: $START_TS"

FAIL=0

# --------------------------------------------
# 0. Working Tree Must Be Clean (fail-closed)
# --------------------------------------------

if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "[precheck] FAILED (working tree dirty)"
  echo "=== TEST HARNESS FAILED ==="
  exit 1
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

if command -v pytest >/dev/null 2>&1; then
  echo "[tests] running pytest..."
  if ! pytest -q; then
    echo "[tests] FAILED"
    FAIL=1
  else
    echo "[tests] OK"
  fi
else
  echo "[tests] pytest unavailable, running unittest fallback..."
  if ! python -m unittest discover -s supervisor/tests -p "test_*.py"; then
    echo "[tests] FAILED"
    FAIL=1
  else
    echo "[tests] OK"
  fi
fi

# --------------------------------------------
# 3. Type Checks (optional)
# --------------------------------------------

if command -v mypy >/dev/null 2>&1 && { [ -f "mypy.ini" ] || [ -f "pyproject.toml" ] || [ -f "setup.cfg" ]; }; then
  echo "[typecheck] running mypy..."
  if ! mypy .; then
    echo "[typecheck] FAILED"
    FAIL=1
  else
    echo "[typecheck] OK"
  fi
else
  if ! command -v mypy >/dev/null 2>&1; then
    echo "[typecheck] skipped (no mypy)"
  else
    echo "[typecheck] skipped (no mypy config)"
  fi
fi

# --------------------------------------------
# 4. Determinism Gate (required, fail-closed)
# --------------------------------------------

if [ ! -f "./scripts/determinism-check.sh" ]; then
  echo "[determinism] FAILED (missing ./scripts/determinism-check.sh)"
  FAIL=1
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
  exit 1
fi

echo "=== TEST HARNESS PASSED ==="
exit 0

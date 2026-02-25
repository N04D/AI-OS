#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: python3/python not found" >&2
  exit 22
fi

# Milestone 1 deterministic test set:
# - evaluator unit/contract tests
# - workflow contract tests
# - docs/workflow drift tests
"$PYTHON_BIN" -m unittest -v \
  tests.test_pr_gate_path_allowlist \
  tests.test_pr_gate_gitea_workflow \
  tests.test_pr_gate_docs_contract

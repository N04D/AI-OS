#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIOS_NIGHT_REPO_ROOT="${AIOS_NIGHT_REPO_ROOT:-$REPO_ROOT_DEFAULT}"
AIOS_NIGHT_WORKSPACE="${AIOS_NIGHT_WORKSPACE:-$AIOS_NIGHT_REPO_ROOT/.night/AI-OS}"
AIOS_NIGHT_BRANCH="${AIOS_NIGHT_BRANCH:-dev}"
AIOS_NIGHT_BOOTSTRAP="${AIOS_NIGHT_BOOTSTRAP:-false}"
AIOS_NIGHT_SOURCE="${AIOS_NIGHT_SOURCE:-local}"
AIOS_NIGHT_AGENT_ID="${AIOS_NIGHT_AGENT_ID:-night-mode}"
AIOS_NIGHT_POLICY_PATH="${AIOS_NIGHT_POLICY_PATH:-governance_policy.yaml}"
AIOS_NIGHT_BUDGET_ENGINE_STATE_PATH="${AIOS_NIGHT_BUDGET_ENGINE_STATE_PATH:-state/budgets.json}"
AIOS_NIGHT_BUDGET_STATE_PATH="${AIOS_NIGHT_BUDGET_STATE_PATH:-state/night_mode_budget_state.json}"
AIOS_NIGHT_CAPABILITY_LEDGER_PATH="${AIOS_NIGHT_CAPABILITY_LEDGER_PATH:-state/supervisor_capabilities.json}"
AIOS_NIGHT_CAPABILITY_DENYLIST_PATH="${AIOS_NIGHT_CAPABILITY_DENYLIST_PATH:-state/supervisor_capability_denies.json}"
AIOS_NIGHT_SPECS_DIR="${AIOS_NIGHT_SPECS_DIR:-state/night_specs}"
AIOS_NIGHT_SUMMARY_DIR="${AIOS_NIGHT_SUMMARY_DIR:-logs/control/night_runs}"
AIOS_NIGHT_REMOTE_CONFIG_PATH="${AIOS_NIGHT_REMOTE_CONFIG_PATH:-config/remote_sources.yaml}"
AIOS_NIGHT_LOG_PATH="${AIOS_NIGHT_LOG_PATH:-$AIOS_NIGHT_REPO_ROOT/logs/cron/night_mode_auto.log}"
AIOS_NIGHT_OPERATOR_EMAIL="${AIOS_NIGHT_OPERATOR_EMAIL:-}"
AIOS_NIGHT_KICK_SCRIPT="${AIOS_NIGHT_KICK_SCRIPT:-$AIOS_NIGHT_REPO_ROOT/tools/codex_night_kick.sh}"
AIOS_NIGHT_REPORT_VALIDATOR="${AIOS_NIGHT_REPORT_VALIDATOR:-$AIOS_NIGHT_REPO_ROOT/workspace/codex/night/tools/validate_morning_report.py}"
AIOS_SKILL_LINTER="${AIOS_SKILL_LINTER:-$AIOS_NIGHT_REPO_ROOT/tools/skill_linter.py}"
AIOS_SKILL_LINTER_ROOT="${AIOS_SKILL_LINTER_ROOT:-$HOME/.codex/skills}"

mkdir -p "$(dirname "$AIOS_NIGHT_LOG_PATH")"

RUN_ROOT="$AIOS_NIGHT_REPO_ROOT"
if [[ "${AIOS_NIGHT_BOOTSTRAP,,}" == "true" ]]; then
  export NIGHT_DIR="$AIOS_NIGHT_WORKSPACE"
  export NIGHT_BRANCH="$AIOS_NIGHT_BRANCH"
  "$AIOS_NIGHT_REPO_ROOT/scripts/night-bootstrap.sh" >>"$AIOS_NIGHT_LOG_PATH" 2>&1
  RUN_ROOT="$AIOS_NIGHT_WORKSPACE"
fi

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] night_mode run start source=$AIOS_NIGHT_SOURCE run_root=$RUN_ROOT"
  cd "$RUN_ROOT"
  export NIGHT_AGENT_ID="$AIOS_NIGHT_AGENT_ID"
  if [[ -n "$AIOS_NIGHT_OPERATOR_EMAIL" ]]; then
    export NIGHT_OPERATOR_EMAIL="$AIOS_NIGHT_OPERATOR_EMAIL"
  fi
  if [[ -x "$AIOS_SKILL_LINTER" ]]; then
    if LINTER_OUT="$("$AIOS_SKILL_LINTER" --root "$AIOS_SKILL_LINTER_ROOT" 2>&1)"; then
      echo "$LINTER_OUT"
      echo "skill-linter ok root=$AIOS_SKILL_LINTER_ROOT"
    else
      echo "$LINTER_OUT"
      echo "skill-linter failed root=$AIOS_SKILL_LINTER_ROOT"
    fi
  else
    echo "skill-linter skipped: missing executable at $AIOS_SKILL_LINTER"
  fi
  set +e
  NIGHT_OUT="$(./scripts/aiosctl --json night-run \
    --source "$AIOS_NIGHT_SOURCE" \
    --policy-path "$AIOS_NIGHT_POLICY_PATH" \
    --budget-engine-state-path "$AIOS_NIGHT_BUDGET_ENGINE_STATE_PATH" \
    --budget-state-path "$AIOS_NIGHT_BUDGET_STATE_PATH" \
    --capability-ledger-path "$AIOS_NIGHT_CAPABILITY_LEDGER_PATH" \
    --capability-denylist-path "$AIOS_NIGHT_CAPABILITY_DENYLIST_PATH" \
    --specs-dir "$AIOS_NIGHT_SPECS_DIR" \
    --summary-dir "$AIOS_NIGHT_SUMMARY_DIR" \
    --remote-config-path "$AIOS_NIGHT_REMOTE_CONFIG_PATH" 2>&1)"
  rc=$?
  set -e
  echo "$NIGHT_OUT"
  if [[ $rc -ne 0 ]]; then
    if python3 - <<'PY' "$NIGHT_OUT"
import json
import sys
raw = sys.argv[1]
try:
    payload = json.loads(raw.strip())
except Exception:
    raise SystemExit(1)
status = str(payload.get("status", "")).strip().lower()
raise SystemExit(0 if status == "halted" else 1)
PY
    then
      rc=0
    fi
  fi
  mapfile -t NIGHT_FIELDS < <(python3 - <<'PY' "$NIGHT_OUT"
import json
import sys
raw = sys.argv[1]
summary_path = ""
status = ""
try:
    payload = json.loads(raw.strip())
    summary_path = str(payload.get("summary_path", "")).strip()
    status = str(payload.get("status", "")).strip()
except Exception:
    pass
print(summary_path)
print(status)
PY
)
  NIGHT_SUMMARY_PATH="${NIGHT_FIELDS[0]:-}"
  NIGHT_STATUS="${NIGHT_FIELDS[1]:-}"
  if [[ -n "$AIOS_NIGHT_KICK_SCRIPT" && -x "$AIOS_NIGHT_KICK_SCRIPT" && -n "$NIGHT_SUMMARY_PATH" ]]; then
    if KICK_OUT="$("$AIOS_NIGHT_KICK_SCRIPT" "$NIGHT_SUMMARY_PATH" "$NIGHT_STATUS" 2>&1)"; then
      echo "$KICK_OUT"
      echo "night-kick ok summary=$NIGHT_SUMMARY_PATH status=${NIGHT_STATUS:-unknown}"
      REPORT_PATH="$(printf '%s\n' "$KICK_OUT" | awk -F= '/^report_path=/{print $2}' | tail -n 1)"
      if [[ -n "$REPORT_PATH" && -x "$AIOS_NIGHT_REPORT_VALIDATOR" ]]; then
        if ! VALIDATE_OUT="$("$AIOS_NIGHT_REPORT_VALIDATOR" "$REPORT_PATH" 2>&1)"; then
          echo "$VALIDATE_OUT"
          echo "night-report validation failed report_path=$REPORT_PATH"
          rc=1
        else
          echo "$VALIDATE_OUT"
          echo "night-report validation ok report_path=$REPORT_PATH"
        fi
      fi
    else
      echo "night-kick failed summary=$NIGHT_SUMMARY_PATH status=${NIGHT_STATUS:-unknown} detail=$KICK_OUT"
    fi
  fi
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] night_mode run done rc=$rc"
  exit $rc
} >>"$AIOS_NIGHT_LOG_PATH" 2>&1

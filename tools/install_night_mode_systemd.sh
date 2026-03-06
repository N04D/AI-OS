#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: tools/install_night_mode_systemd.sh [options]

Options:
  --repo-root <path>        Repo root (default: current git root)
  --on-calendar <expr>      systemd OnCalendar (default: *-*-* 02:30:00)
  --source <mode>           night-run source: local|remote|both|gitea (default: local)
  --night-dir <path>        bootstrap workspace path (default: <repo>/.night/AI-OS)
  --night-branch <name>     bootstrap branch (default: dev)
  --no-bootstrap            disable night-bootstrap before run (default)
  --run-now                 trigger one immediate service run after install
  --no-start                do not enable/start timer immediately
EOF
}

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ON_CALENDAR="*-*-* 02:30:00"
SOURCE="local"
NIGHT_DIR=""
NIGHT_BRANCH="dev"
BOOTSTRAP="false"
RUN_NOW="false"
START_NOW="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT="$2"
      shift 2
      ;;
    --on-calendar)
      ON_CALENDAR="$2"
      shift 2
      ;;
    --source)
      SOURCE="$2"
      shift 2
      ;;
    --night-dir)
      NIGHT_DIR="$2"
      shift 2
      ;;
    --night-branch)
      NIGHT_BRANCH="$2"
      shift 2
      ;;
    --no-bootstrap)
      BOOTSTRAP="false"
      shift
      ;;
    --run-now)
      RUN_NOW="true"
      shift
      ;;
    --no-start)
      START_NOW="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$NIGHT_DIR" ]]; then
  NIGHT_DIR="$REPO_ROOT/.night/AI-OS"
fi

CONFIG_DIR="$HOME/.config/aios"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
ENV_FILE="$CONFIG_DIR/night_mode.env"
SERVICE_FILE="$SYSTEMD_USER_DIR/aios-night-mode.service"
TIMER_FILE="$SYSTEMD_USER_DIR/aios-night-mode.timer"
ENTRYPOINT="$REPO_ROOT/tools/night_mode_systemd_entry.sh"

mkdir -p "$CONFIG_DIR" "$SYSTEMD_USER_DIR"

cat >"$ENV_FILE" <<EOF
AIOS_NIGHT_REPO_ROOT=$REPO_ROOT
AIOS_NIGHT_WORKSPACE=$NIGHT_DIR
AIOS_NIGHT_BRANCH=$NIGHT_BRANCH
AIOS_NIGHT_BOOTSTRAP=$BOOTSTRAP
AIOS_NIGHT_SOURCE=$SOURCE
AIOS_NIGHT_AGENT_ID=night-mode
AIOS_NIGHT_POLICY_PATH=governance_policy.yaml
AIOS_NIGHT_BUDGET_ENGINE_STATE_PATH=state/budgets.json
AIOS_NIGHT_BUDGET_STATE_PATH=state/night_mode_budget_state.json
AIOS_NIGHT_CAPABILITY_LEDGER_PATH=state/supervisor_capabilities.json
AIOS_NIGHT_CAPABILITY_DENYLIST_PATH=state/supervisor_capability_denies.json
AIOS_NIGHT_SPECS_DIR=state/night_specs
AIOS_NIGHT_SUMMARY_DIR=logs/control/night_runs
AIOS_NIGHT_REMOTE_CONFIG_PATH=config/remote_sources.yaml
AIOS_NIGHT_LOG_PATH=$REPO_ROOT/logs/cron/night_mode_auto.log
AIOS_NIGHT_OPERATOR_EMAIL=
AIOS_NIGHT_KICK_SCRIPT=$REPO_ROOT/tools/codex_night_kick.sh
AIOS_NIGHT_REPORT_VALIDATOR=$REPO_ROOT/workspace/codex/night/tools/validate_morning_report.py
AIOS_SKILL_LINTER=$REPO_ROOT/tools/skill_linter.py
AIOS_SKILL_LINTER_ROOT=$HOME/.codex/skills
EOF

cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=AI-OS Night Mode Run
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$REPO_ROOT
EnvironmentFile=$ENV_FILE
ExecStart=$ENTRYPOINT
NoNewPrivileges=true
EOF

cat >"$TIMER_FILE" <<EOF
[Unit]
Description=AI-OS Night Mode Schedule

[Timer]
OnCalendar=$ON_CALENDAR
Persistent=true
Unit=aios-night-mode.service

[Install]
WantedBy=timers.target
EOF

chmod +x "$ENTRYPOINT"
systemctl --user daemon-reload

if [[ "${START_NOW,,}" == "true" ]]; then
  systemctl --user enable --now aios-night-mode.timer
else
  systemctl --user enable aios-night-mode.timer
fi

if [[ "${RUN_NOW,,}" == "true" ]]; then
  systemctl --user start aios-night-mode.service
fi

echo "installed: $SERVICE_FILE"
echo "installed: $TIMER_FILE"
echo "env: $ENV_FILE"
echo "schedule: $ON_CALENDAR"
systemctl --user list-timers aios-night-mode.timer --no-pager || true

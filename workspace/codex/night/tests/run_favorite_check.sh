#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="${1:-$ROOT/reports/$(date -u +%Y-%m-%d).md}"

"$ROOT/tools/validate_morning_report.py" "$REPORT_PATH"

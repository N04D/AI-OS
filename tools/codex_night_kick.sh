#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: tools/codex_night_kick.sh <night_summary_path> [night_status]" >&2
  exit 2
fi

SUMMARY_PATH="$1"
NIGHT_STATUS="${2:-unknown}"
if [[ ! -f "$SUMMARY_PATH" ]]; then
  echo "summary not found: $SUMMARY_PATH" >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "error: run inside repo checkout" >&2
  exit 2
fi

WORKSPACE_LOG="${AIOS_NIGHT_KICK_WORKSPACE_LOG:-workspace/codex/night/kick_responses.jsonl}"
REPORT_DIR="${AIOS_NIGHT_KICK_REPORT_DIR:-workspace/codex/night/reports}"
PROMPT_FILE="$(mktemp)"
OUT_FILE="$(mktemp)"
SUMMARY_JSON_FILE="$(mktemp)"
REPORT_FILE=""

python3 - <<'PY' "$SUMMARY_PATH" "$SUMMARY_JSON_FILE"
import json
import sys
from pathlib import Path

summary = {}
try:
    summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    summary = {}
Path(sys.argv[2]).write_text(json.dumps(summary, sort_keys=True, ensure_ascii=True), encoding="utf-8")
PY

cat >"$PROMPT_FILE" <<EOF
Night-run morning report.

Status: $NIGHT_STATUS
Summary file:
$SUMMARY_PATH

Taak:
- Schrijf in het Nederlands, compact en concreet.
- Gebruik exact deze secties:
  1) "Night-run Resultaat"
  2) "Uitgevoerde Taken"
  3) "10 Ideeën Voor Vandaag"
  4) "Mijn Favoriet Om Nu Te Bouwen"
  5) "Aanbevolen Volgorde"
- "Night-run Resultaat": noem status + kernmetrics (tasks_executed/tasks_failed/violations).
- "Uitgevoerde Taken": som uitgevoerde taken op; als leeg, zeg expliciet dat er niets uitgevoerd is.
- "10 Ideeën Voor Vandaag": precies 10 genummerde ideeën.
  Verdeel over: skills, modules, kernel, test/infra.
  Elk idee: titel + 1 regel waarom + 1 korte acceptatiecheck.
- "Mijn Favoriet Om Nu Te Bouwen": kies exact 1 idee uit de 10 en geef:
  - waarom dit nu de beste keuze is
  - eerste concrete implementatiestap in deze workspace
- "Aanbevolen Volgorde": top 3 ideeën om vandaag te testen/implementeren.
- Geen algemene disclaimer, geen markdown codeblock.

Samenvatting JSON:
$(cat "$SUMMARY_JSON_FILE")
EOF

cd "$REPO_ROOT"
if ! codex exec --cd "$REPO_ROOT" --full-auto --output-last-message "$OUT_FILE" - <"$PROMPT_FILE"; then
  printf '%s\n' "Night-run kick: samenvatting niet beschikbaar door uitvoerfout." >"$OUT_FILE"
fi

python3 - <<'PY' "$OUT_FILE"
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8").strip() if p.exists() else ""

mapping = {
    "night-run resultaat": "**Night-run Resultaat**",
    "uitgevoerde taken": "**Uitgevoerde Taken**",
    "10 ideeën voor vandaag": "**10 Ideeën Voor Vandaag**",
    "mijn favoriet om nu te bouwen": "**Mijn Favoriet Om Nu Te Bouwen**",
    "aanbevolen volgorde": "**Aanbevolen Volgorde**",
}

lines = []
for raw in text.splitlines():
    line = raw.strip()
    lowered = re.sub(r"^[#0-9\).\s:-]+", "", line.lower())
    replaced = None
    for key, canonical in mapping.items():
        if lowered.startswith(key):
            replaced = canonical
            break
    lines.append(replaced if replaced is not None else raw.rstrip())

normalized = "\n".join(lines).strip()
if normalized:
    p.write_text(normalized + "\n", encoding="utf-8")
PY

python3 - <<'PY' "$WORKSPACE_LOG" "$SUMMARY_PATH" "$NIGHT_STATUS" "$OUT_FILE"
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

log_path = Path(sys.argv[1])
summary_path = sys.argv[2]
night_status = sys.argv[3]
out_file = Path(sys.argv[4])
message = out_file.read_text(encoding="utf-8").strip() if out_file.exists() else ""
record = {
    "ts_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "type": "night_kick",
    "night_status": night_status,
    "summary_path": summary_path,
    "response": message,
}
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
PY

REPORT_FILE="$(python3 - <<'PY' "$REPORT_DIR" "$OUT_FILE"
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

report_dir = Path(sys.argv[1])
out_file = Path(sys.argv[2])
text = out_file.read_text(encoding="utf-8").strip() if out_file.exists() else ""
stamp = datetime.now(UTC).strftime("%Y-%m-%d")
report_dir.mkdir(parents=True, exist_ok=True)
report_path = report_dir / f"{stamp}.md"
header = f"# Morning Night-Run Report ({stamp})\n\n"
report_path.write_text(header + (text or "Geen rapport beschikbaar.") + "\n", encoding="utf-8")
print(str(report_path))
PY
)"

cat "$OUT_FILE"
echo
echo "report_path=$REPORT_FILE"

rm -f "$PROMPT_FILE" "$OUT_FILE" "$SUMMARY_JSON_FILE"

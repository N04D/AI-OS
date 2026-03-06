#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: tools/codex_email_kick.sh <email_artifact_path>" >&2
  exit 2
fi

ARTIFACT_PATH="$1"
if [[ ! -f "$ARTIFACT_PATH" ]]; then
  echo "artifact not found: $ARTIFACT_PATH" >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "error: run inside repo checkout" >&2
  exit 2
fi

WEBHOOK_URL="${AIOS_EMAIL_KICK_WEBHOOK_URL:-}"
WEBHOOK_TOKEN="${AIOS_EMAIL_KICK_WEBHOOK_TOKEN:-}"
WORKSPACE_LOG="${AIOS_EMAIL_KICK_WORKSPACE_LOG:-workspace/codex/mail/inbox/kick_responses.jsonl}"
AUTO_REPLY="${AIOS_EMAIL_KICK_AUTO_REPLY:-true}"

PROMPT_FILE="$(mktemp)"
OUT_FILE="$(mktemp)"
cat >"$PROMPT_FILE" <<EOF
Nieuwe email binnen (channel kick).

Lees dit artifact:
$ARTIFACT_PATH

Taak:
- Schrijf ALLEEN de replytekst die per email verstuurd moet worden.
- Geen samenvatting, geen uitleg, geen markdown, geen nummering.
- Maximaal 6 korte regels.
- Neutraal en vriendelijk Nederlands.
EOF

cd "$REPO_ROOT"
if ! codex exec --cd "$REPO_ROOT" --full-auto --output-last-message "$OUT_FILE" - <"$PROMPT_FILE"; then
  echo "warning: codex exec failed; using fallback reply text" >&2
  printf '%s\n' "Je bericht is ontvangen en verwerkt. Bedankt voor je mail." >"$OUT_FILE"
fi

python3 - <<'PY' "$WORKSPACE_LOG" "$ARTIFACT_PATH" "$OUT_FILE"
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

log_path = Path(sys.argv[1])
artifact_path = sys.argv[2]
out_file = Path(sys.argv[3])
message = ""
if out_file.exists():
    message = out_file.read_text(encoding="utf-8").strip()
record = {
    "ts_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "type": "email_kick",
    "artifact_path": artifact_path,
    "response": message,
}
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
PY

if [[ "${AUTO_REPLY,,}" == "true" ]]; then
  if python3 - <<'PY' "$ARTIFACT_PATH"
import json
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
subject = str(payload.get("subject", "")).strip().lower()
body = str(payload.get("body", "")).strip().lower()
text = f"{subject}\n{body}"
blockers = (
    "hoeft niet",
    "niet nodig",
    "laat maar",
    "laat het hierbij",
    "geen reactie nodig",
    "niet antwoorden",
    "no reply needed",
    "no need to reply",
)
for token in blockers:
    if token in text:
        raise SystemExit(10)
raise SystemExit(0)
PY
  then
    :
  else
    code=$?
    if [[ $code -eq 10 ]]; then
      echo "auto-reply skipped: sender indicated no reply needed"
      exit 0
    fi
    echo "auto-reply guard failed: parser error code=$code" >&2
    exit $code
  fi

  mapfile -t MAIL_FIELDS < <(python3 - <<'PY' "$ARTIFACT_PATH"
import json
import sys
payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
sender = str(payload.get("from", "")).strip()
subject = str(payload.get("subject", "")).strip()
print(sender)
print(subject)
PY
)
  TO_ADDR="${MAIL_FIELDS[0]:-}"
  ORIG_SUBJECT="${MAIL_FIELDS[1]:-}"
  if [[ -n "$TO_ADDR" ]]; then
    REPLY_SUBJECT="$ORIG_SUBJECT"
    if [[ "${REPLY_SUBJECT,,}" != re:* ]]; then
      REPLY_SUBJECT="Re: ${REPLY_SUBJECT:-update}"
    fi
    REPLY_BODY="$(python3 - <<'PY' "$OUT_FILE"
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8").strip() if p.exists() else ""
if not text:
    text = "Je bericht is ontvangen en verwerkt."

drop_prefixes = (
    "#", "##", "###",
    "1.", "2.", "3.", "4.", "5.", "6.",
    "-", "*",
    "onderwerp:", "subject:",
    "korte samenvatting", "samenvatting",
    "is actie nodig", "actie nodig",
    "klaar-om-te-versturen", "concreet voorstel",
)
cleaned = []
for raw in text.splitlines():
    line = raw.strip()
    if not line:
        continue
    low = line.lower()
    if low.startswith(drop_prefixes):
        continue
    cleaned.append(line)

out = "\n".join(cleaned[:6])[:2000].strip()
if not out:
    out = "Je bericht is ontvangen en verwerkt."
print(out)
PY
)"
    if QUEUE_RESULT="$(./tools/email_safe_run.sh send --agent codex --to "$TO_ADDR" --subject "$REPLY_SUBJECT" --body "$REPLY_BODY" 2>&1)"; then
      echo "auto-reply queued to=$TO_ADDR subject=$REPLY_SUBJECT result=$QUEUE_RESULT"
    else
      echo "auto-reply queue failed to=$TO_ADDR subject=$REPLY_SUBJECT error=$QUEUE_RESULT" >&2
      exit 1
    fi
  else
    echo "auto-reply skipped: missing sender in artifact=$ARTIFACT_PATH" >&2
  fi
fi

if [[ -n "$WEBHOOK_URL" ]]; then
  python3 - <<'PY' "$WEBHOOK_URL" "$WEBHOOK_TOKEN" "$ARTIFACT_PATH" "$OUT_FILE"
import json
import sys
import urllib.request

url = sys.argv[1]
token = sys.argv[2]
artifact_path = sys.argv[3]
out_file = sys.argv[4]
message = ""
try:
    message = open(out_file, "r", encoding="utf-8").read().strip()
except Exception:
    message = ""
payload = {
    "type": "email_kick",
    "artifact_path": artifact_path,
    "response": message,
}
data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
req = urllib.request.Request(url=url, data=data, method="POST")
req.add_header("Content-Type", "application/json")
if token:
    req.add_header("Authorization", f"Bearer {token}")
with urllib.request.urlopen(req, timeout=15) as resp:
    resp.read()
PY
fi

rm -f "$PROMPT_FILE"
rm -f "$OUT_FILE"

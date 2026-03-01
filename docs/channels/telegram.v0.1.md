# Telegram Channel v0.1

## Purpose
Provide a controlled external ingress boundary for Telegram webhook updates.
Ingress converts accepted updates into one internal event only:
`channel.telegram.message`.

## Non-Goals
- No direct `dispatch()` calls.
- No plugin selection.
- No method selection.
- No skill routing.
- No plugin enable/disable control.

## Routing Model
`POST /webhook/telegram` -> `kernel.channels.telegram.parse_update(...)` ->
`kernel.events.emit("channel.telegram.message", payload=...)` ->
event subscriptions -> fixed `on_event` dispatch.

## Security Controls
- Shared-secret header auth:
  - Header: `X-AIOS-TELEGRAM-SECRET`
  - Env: `AIOS_TELEGRAM_WEBHOOK_SECRET`
  - Constant-time comparison.
- Chat allowlist:
  - Env: `AIOS_TELEGRAM_ALLOWED_CHAT_IDS`
  - Comma-separated integer chat IDs.
- Deterministic ingress audit log:
  - `logs/control/channel-telegram.jsonl`
  - No raw payload logging.
- Event bus audit remains in:
  - `logs/control/kernel-events.jsonl`

## Required Environment
- `AIOS_TELEGRAM_WEBHOOK_SECRET` (required)
- `AIOS_TELEGRAM_ALLOWED_CHAT_IDS` (required)

## Optional Environment
- `AIOS_REGISTRY_PATH` (default: `state/plugins/registry.json`)
- `AIOS_CONFIG_PATH` (default: `state/plugins/config.json`)
- `AIOS_EVENT_AUDIT_LOG_PATH` (default: `logs/control/kernel-events.jsonl`)
- `AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH` (default: `logs/control/channel-telegram.jsonl`)

## Example Plugin Manifest Snippet
```yaml
subscriptions:
  - channel.telegram.message
methods:
  - on_event
```

## Local Test Request
```bash
curl -X POST http://127.0.0.1:8000/webhook/telegram \
  -H 'Content-Type: application/json' \
  -H 'X-AIOS-TELEGRAM-SECRET: your-secret' \
  -d '{
    "update_id": 123,
    "message": {
      "message_id": 9,
      "date": 1710000000,
      "chat": {"id": 111111},
      "from": {"id": 222222},
      "text": "hello"
    }
  }'
```

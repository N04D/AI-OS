# Event Bus v0.1

## Purpose
Provide an internal-only event fan-out API that routes kernel events to enabled plugins through `kernel.dispatch.dispatch()`.

## Non-Goals
- No channel integration (Telegram/webhooks/etc).
- No skill system routing.
- No auto-enable behavior.
- No runner behavior changes.

## API
```python
emit(
  event_type: str,
  payload: dict,
  *,
  registry_path="state/plugins/registry.json",
  config_path="state/plugins/config.json",
  audit_log_path="logs/control/kernel-events.jsonl",
) -> dict
```

## Event Object
For each delivery attempt, event bus builds:
```json
{
  "event_id": "uuid",
  "type": "event.type",
  "payload": {},
  "ts": "RFC3339 UTC"
}
```

Method name is fixed: `on_event`.

## Subscription Semantics
- Subscriptions are read from plugin manifest top-level field:
  - `subscriptions: ["event.a", "event.b"]`
- Missing `subscriptions` => no event delivery (fail-closed).
- Non-matching `event_type` => no delivery.
- Manifest parse/read failure => plugin marked failed.

## Enabled + Trust Rules
- Candidates come from effective enabled set (registry + config).
- Config supports:
  - `plugins.{plugin_id}.enabled == true`
  - optional legacy `enabled: ["plugin_id"]`
- External plugins require `unsafe_allow_external: true`.

## Audit Behavior
- Audit file: `logs/control/kernel-events.jsonl`.
- Logged fields exclude payload contents.
- Logged events:
  - `emit_start`
  - per-plugin `deliver` with `duration_ms`, `ok`, `error_code`
  - `emit_end` summary counts
- If audit log cannot be written initially, emission fails closed and no delivery occurs.

## Determinism
- Plugin processing order is `plugin_id` ascending.
- `delivered` and `failed` arrays are sorted by `plugin_id`.
- Audit JSON lines are written with `sort_keys=True`.

## Response Shape
```json
{
  "ok": true,
  "event_id": "...",
  "event_type": "...",
  "delivered": [
    {"plugin_id":"...", "ok":true, "error_code":null}
  ],
  "failed": [
    {"plugin_id":"...", "error_code":"...", "details":[]}
  ]
}
```

## Example
```python
from kernel.events import emit

resp = emit("test.event", {"kind": "probe"})
```

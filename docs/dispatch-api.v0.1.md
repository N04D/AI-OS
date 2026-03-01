# Dispatch API v0.1

## Scope
Internal kernel integration point for plugin invocation.
This API is intentionally local-only and deterministic.

## What It Is
- A single function: `kernel.dispatch.dispatch(...)`
- Uses secure runner: `kernel/plugins/runner.py`
- Converts runner outcomes into a stable caller contract

## What It Is Not
- Not a channel gateway (no Telegram, no inbound webhooks)
- Not a skill dispatcher/router
- Not an auto-enable mechanism
- Not a secrets transport

## Function Contract
`dispatch(plugin_id, method, payload, *, request_id=None, registry_path="state/plugins/registry.json", config_path="state/plugins/config.json", audit_log_path="logs/control/plugin-runtime.jsonl", runner_state_dir_base="state/plugins/runtime", timeout_override_seconds=None) -> dict`

Input validation (fail-closed):
- `plugin_id`: non-empty string
- `method`: non-empty string
- `payload`: object/dict
- `timeout_override_seconds`: if provided, must be positive integer

Request sent to runner:
```json
{"type":"request","id":"...","method":"...","payload":{}}
```

## Response Contract
Success:
```json
{
  "ok": true,
  "plugin_id": "echo-ok",
  "request_id": "req-...",
  "result": {}
}
```

Failure:
```json
{
  "ok": false,
  "plugin_id": "echo-ok",
  "request_id": "req-...",
  "error": {
    "code": "DISPATCH_*",
    "message": "...",
    "details": ["RUNNER_REASON_CODE", "..."]
  }
}
```

## Error Mapping Rules
- Invalid caller args => `DISPATCH_INVALID_ARGS`
- Method blocked by capability gate => `METHOD_NOT_ALLOWED`
- Runner refusal/policy/safety deny => `DISPATCH_RUNNER_REFUSED`
- Runner execution/runtime failure => `DISPATCH_RUNNER_ERROR`
- Unexpected dispatch exception => `DISPATCH_INTERNAL_ERROR`

Runner reason codes are preserved in `error.details[0]`.

## Capability Gate (Method-Level Enforcement)
- Dispatch enforces plugin method allowlist before runner invocation.
- Source of truth: plugin manifest field `methods` (optional):
  - `methods: ["on_event", "notify"]`
- Rule:
  - If `methods` exists and is valid, only listed methods are allowed.
  - If `methods` is missing, unreadable, or invalid, fail-closed default is:
    - allowed methods = `["on_event"]`
- If requested method is not allowed:
  - dispatch returns `ok:false` with error code `METHOD_NOT_ALLOWED`
  - no runner call is attempted
  - no plugin subprocess is spawned

## Determinism Guarantees
- If `request_id` is omitted, request ID is derived from a canonical hash of:
  `plugin_id`, `method`, `payload`.
- JSON request shape is stable.
- Failure responses always include `ok`, `plugin_id`, `request_id`, `error`.

## Example
```python
from kernel.dispatch import dispatch

resp = dispatch("echo-ok", "ping", {"x": 1})
```

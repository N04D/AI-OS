# 05 Event Bus

## Purpose
Describe event production, routing, auditing, and deterministic failure handling in the kernel event bus.

## Current Behavior

### Event model
- Primary emitter: `kernel.events.emit(event_type, payload, ...)`.
- Event envelope fields:
  - `event_id` (uuid)
  - `type`
  - `payload`
  - `ts` (UTC RFC3339)
- Scheduler emits `scheduler.job_due` envelopes through this path where available.

### Delivery path

```text
emit_start audit record
  -> read plugin registry/config
  -> select enabled plugins
  -> enforce external plugin allowance
  -> load manifest subscriptions
  -> dispatch on_event to subscribed plugins
  -> deliver audit records per plugin
emit_end audit record
```

### Fallback behavior from scheduler CLI
- If importing `kernel.events.emit` fails, scheduler writes append-only JSON event records to:
  `logs/control/events/<date>/scheduler.job_due__<job_id>__<ts>.json`

## Fail-Closed Rules
- Invalid emit args fail with `EVENT_BUS_INVALID_ARGS`.
- Registry/config unreadable states fail with explicit event-bus error codes.
- Audit write failure in start/delivery/end transitions fails closed.
- External plugins are blocked unless config explicitly allows them.

## Security Boundaries
- Event bus routes only to enabled plugins and declared subscriptions.
- Dispatch call remains gated by plugin manifest method policy.
- Event emission does not grant mutation authority by itself.

## Determinism Guarantees
- Delivery and failure arrays are sorted before result return.
- Event logging structure is stable and append-only.
- Plugin selection is deterministic based on sorted identifiers and config.

## Known Limitations / TODOs
- Event bus timestamps use runtime UTC now; replay determinism relies on recorded artifacts rather than recomputation.
- Event bus currently depends on plugin registry/config presence for routed delivery.

## Cross-links
- [02 Plugin Lifecycle](./02-Plugin-Lifecycle.md)
- [04 Dispatch and Capability Gate](./04-Dispatch-and-Capability-Gate.md)
- [06 Operator Config and Audit](./06-Operator-Config-and-Audit.md)

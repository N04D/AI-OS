# Secrets EventBus Adapter v1

This contract defines the planned event sink shape for secrets telemetry.

Planned interfaces:
- `EventSink.emit(event: dict) -> None`
- Multiplexing sink fan-out behavior
- Supervisor file sink compatibility

Contract notes:
- Emission failures must not leak secret material.
- Emit failure should map to stable reason code `EVENTBUS_EMIT_FAILED`.
- Event payloads must conform to `secrets_events.v1.json`.

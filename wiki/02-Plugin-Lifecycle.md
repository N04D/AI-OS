# 02 Plugin Lifecycle

## Purpose
Describe deterministic plugin discovery, validation, registration, dispatch, and runtime failure behavior.

## Current Behavior

### Lifecycle flow

```text
plugin source dirs
  -> supervisor.plugin_loader.discover_plugins()
     -> schema + policy readable checks
     -> validate_manifest()
     -> collision resolution (repo/external + trust tier priority)
     -> write state/plugins/registry.json

runtime dispatch
  -> kernel.events.emit(event)
     -> registry + config read
     -> enabled plugin selection
     -> subscription check
     -> kernel.dispatch(plugin_id, method, payload)
     -> PluginRunner request/response
     -> audit logs in logs/control/*.jsonl
```

### Discovery and registry
- Default scan dirs: `plugins` and `/var/lib/ai-os/plugins`.
- Manifest schema: `governance/schema/plugins/plugin-manifest.v0.1.yaml`.
- Boundary policy: `governance/policy/plugins/plugin-boundary.v0.1.yaml`.
- Registry path: `state/plugins/registry.json`.
- Enabled/disabled state persisted via CLI plugin enable/disable commands.

### Dispatch constraints
- Method gate: `kernel.dispatch` only allows methods declared in manifest `methods` (default `on_event`).
- External plugins can be blocked unless config enables `unsafe_allow_external`.
- Runner refusals are mapped to dispatch error families (`DISPATCH_RUNNER_REFUSED` / `DISPATCH_RUNNER_ERROR`).

## Fail-Closed Rules
- Missing schema/policy/config/registry produces explicit deny/error outcomes.
- Invalid manifest or missing command denies plugin activation.
- Invalid method invocation is refused.
- Audit write failures in event emit path mark emit as failed.

## Security Boundaries
- Plugins run out-of-process via subprocess runner.
- Policy restricts forbidden paths and disallowed protocols.
- Dispatch does not grant direct bypass around capability governance or secure execution permit checks.

## Determinism Guarantees
- Registry entries are sorted deterministically.
- Event delivery results are sorted before return.
- Request IDs are deterministic when caller omits request ID (derived from plugin+method+payload hash).

## Known Limitations / TODOs
- `state/plugins/config.json` and `state/plugins/registry.json` may not exist until plugins are initialized.
- External plugin allowance is global in config, not fine-grained per capability.

## Cross-links
- [05 Event Bus](./05-Event-Bus.md)
- [04 Dispatch and Capability Gate](./04-Dispatch-and-Capability-Gate.md)
- [07 Error Code Registry](./07-Error-Code-Registry.md)

# Plugin Ops v0.1

## Purpose
Operator-facing control plane for discovered plugins using local files and CLI only.

## State Files
- Registry: `state/plugins/registry.json`
- Operator config: `state/plugins/config.json`

`registry.json` is discovery output. It is read-only for operators.
`config.json` is operator-owned enablement state.

## Registry vs Config
- `registry.json` contains discovered plugin metadata (`plugin_id`, `version`, `trust_tier`, `path`, `fingerprint`, `api_version`).
- `config.json` canonical shape:
  - `enabled`: list of plugin IDs
  - `unsafe_allow_external`: boolean

Canonical `config.json`:
```json
{
  "enabled": ["plugin-a"],
  "unsafe_allow_external": false
}
```

Backward-compatible reads also accept legacy:
```json
{
  "plugins": {
    "plugin-a": {"enabled": true}
  },
  "unsafe_allow_external": false
}
```
Writes are canonical only.

Registry `enabled` fields are informational only.

## Enable/Disable Workflow
1. Refresh discovery into `registry.json`.
2. Use CLI:
   - `python scripts/aios_plugins.py list`
   - `python scripts/aios_plugins.py enable <plugin_id>`
   - `python scripts/aios_plugins.py disable <plugin_id>`
   - `python scripts/aios_plugins.py set-unsafe-external true|false`

## External Plugin Semantics
- External plugins are denied by default.
- `enable <id>` for trust tier `external` requires `unsafe_allow_external=true`.
- `enabled_effective` is true only if plugin is enabled and trust policy permits it.

## Audit Log
- Append-only JSONL: `logs/control/plugin-events.jsonl`
- Event fields:
  - `ts`, `actor`, `action`, `plugin_id` (optional), `trust_tier` (optional),
    `result`, `reason_code`, `details`
- Payload contents are not logged.

## Determinism + Fail-Closed
- Config writes are atomic and deterministic (`indent=2`, `sort_keys=True`).
- If audit write fails, config mutation is denied.
- Invalid config/registry shape fails closed.

## Path Overrides (Testing/Automation)
All CLI commands accept:
- `--registry-path`
- `--config-path`
- `--audit-log-path`

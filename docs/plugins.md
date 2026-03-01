# Plugins v0.1

Plugins are governed extensions that must stay outside kernel control boundaries.

## Discovery and Registry

Loader scans manifests from:

1. `./plugins` (repo)
2. `/var/lib/ai-os/plugins` (external)

Discovery target is `*/plugin.yaml`.

All manifests are validated against:

- `governance/schema/plugins/plugin-manifest.v0.1.yaml`
- `governance/policy/plugins/plugin-boundary.v0.1.yaml`

Validation is fail-closed. Missing/unreadable schema or policy denies by default.

Resolved registry is persisted to:

- `state/plugins/registry.json`

Collision rule:

- same `plugin_id` from multiple sources: repo plugin wins over external.
- if still tied, deterministic ordering by path is used.

## Trust Tiers

- `official`: signed registry packages only.
- `community`: externally sourced, restricted by manifest policy.
- `local`: host-local plugin for development/testing.

## Signed Registry Rule

Official plugins must have `signing.registry_signed: true` in `plugin.yaml`.
Unsigned official manifests are denied.

## Unsafe Opt-In

Non-official installs (`community`, `local`) are treated as unsafe opt-in and are still constrained by boundary policy:

- forbidden capabilities are denied
- forbidden filesystem paths are denied
- wildcard network access is denied
- explicit network allow list is required

## Isolation Boundary

Plugins are out-of-process (`execution.out_of_process: true`) and may not modify kernel or runtime internals.

Forbidden path families:

- `kernel/**`
- `governance/core/**`
- `executor/runtime/**`

PR-Gate check `pr-gate/plugin-boundary` validates changed plugin manifests and blocks merge on denial.

## Runtime Model (MVP)

Plugins run out-of-process only (no in-process imports).

- Process spawned on demand from manifest command.
- IPC protocol: NDJSON over `stdin`/`stdout`.
- Request envelope:
  - `{"type":"request","id":"<uuid>","capability":"notify:escalation","payload":{...}}`
- Response envelope:
  - `{"id":"<uuid>","ok":true|false,...}`

MVP capability dispatch allows only:

- `notify:escalation`

Reliability behavior:

- per-request timeout
- limited restart retries
- auto-disable plugin on repeated failures

Path safety:

- artifact paths from plugin responses are sanitized
- absolute paths and path escapes (`..`) are denied

## CLI

Use `aiosctl` plugin commands:

- `aiosctl plugin validate`
- `aiosctl plugin list`
- `aiosctl plugin enable <plugin_id>`
- `aiosctl plugin disable <plugin_id>`

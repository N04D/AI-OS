# 06 Operator Config and Audit

## Purpose
Define operator-facing configuration contracts and audit artifact formats currently used by autonomy, scheduler, plugins, and budgets.

## Current Behavior

### Key config/state files
- `state/scheduler_jobs.json`
  - Shape: `{version:"v0.1", timezone:"UTC", jobs:[...]}`
  - `jobs[*].mode` in `{event_only, guarded_skill}`
- `state/scheduler_state.json`
  - Shape: `{version:"v0.1", last_run_utc, jobs:{job_id:{last_fired_utc}}}`
- `state/budgets.json` (Phase J)
  - Shape: `{version:"v0.1", timezone:"UTC", budgets:{<key>:{window,limit,used,window_start_utc}}}`
- `state/supervisor_capabilities.json`
  - Capability grant ledger (bool and object forms supported)
- `state/supervisor_capability_denies.json` (optional)
  - Shape: `{deny:[capability...], updated_at?}`
- `governance_policy.yaml` (Phase K)
  - Strict keyset policy for trust/risk/skill quotas/ledger behavior
- `config/channels/email_gateway.json`
  - Email gateway module toggle + per-agent enable flags
- `governance/policy/email_gateway.v0.1.json`
  - Send/receive/reply allowlist policy envelope

### Plugin config and registry
- Registry: `state/plugins/registry.json` (written by discovery/enable/disable flows)
- Runtime config: `state/plugins/config.json` (read by event bus and dispatch)
- If missing/unreadable, event bus fails closed.

### Audit artifacts
- Kernel event bus: `logs/control/kernel-events.jsonl`
- Plugin runtime dispatch: `logs/control/plugin-runtime.jsonl`
- Scheduler event fallback: `logs/control/events/<date>/...json`
- Scheduler guarded_skill runs: `logs/control/scheduler_runs/<date>/...json`
- Secure execution stream artifacts: `audit/streams/<stream_id>/<sequence>.audit.json`
- Phase K budget ledger: `audit/budget_ledger/<epoch>.jsonl`
- Email gateway audit: `logs/control/email_gateway_audit.jsonl`
- Email gateway outbox artifacts: `runtime/channels/email_gateway/outbox/<agent>/...json`
- Email gateway inbox artifacts: `runtime/channels/email_gateway/inbox/<agent>/...json`
- Local worker queue artifacts: `workspace/<agent>/mail/{outbox,sent,failed}/*.json`

### Email auto-loop (systemd user service)
- Unit: `aios-email-auto.service`
- Unit file: `~/.config/systemd/user/aios-email-auto.service`
- Runtime env: `~/.config/aios/email_auto.env` (`0600`)
- Entry script: `tools/email_auto_systemd_entry.sh`
- Installer script: `tools/install_email_auto_systemd.sh`
- Install/start:
  - `tools/install_email_auto_systemd.sh install --smtp-user nova69.agent@gmail.com --smtp-from nova69.agent@gmail.com --agent codex`
- Status:
  - `tools/install_email_auto_systemd.sh status`
- Live logs:
  - `journalctl --user -u aios-email-auto.service -f`
- Uninstall:
  - `tools/install_email_auto_systemd.sh uninstall`

### Phase K ledger entry contract
- JSONL, append-only, per epoch.
- Each event includes `hash_prev` and `hash` where:
  - `hash = sha256(canonical_json(event_without_hash))`
  - `event_without_hash` includes `hash_prev`
- Canonical JSON settings are policy-bound and enforced by engine.

## Fail-Closed Rules
- Missing policy/state files in Phase K raise deny errors.
- Invalid scheduler/job/state JSON rejects ticks.
- Audit write failures return explicit error/deny outcomes.
- Budget consumption writes only after validation; invalid state denies.
- Email gateway denies on module/agent/capability/policy violations and writes deny audit events.

## Security Boundaries
- Config files are treated as governance inputs; malformed files are denied.
- Audit streams are append-only in design; overwrite violations in secure layer trigger kill-switch.
- Operator tooling does not bypass capability or mutation boundaries.

## Determinism Guarantees
- JSON outputs are sorted and stable where written by budget/scheduler paths.
- Phase K uses canonical JSON + deterministic hash chaining.
- UTC-only time normalization in scheduler and budget modules.

## Known Limitations / TODOs
- Multiple budget systems coexist (legacy autonomy budget and Phase J/Phase K stores).
- Phase K read-only CLI exists in module but is not wired into `scripts/aiosctl` yet.

## Cross-links
- [01 Governance Model](./01-Governance-Model.md)
- [05 Event Bus](./05-Event-Bus.md)
- [07 Error Code Registry](./07-Error-Code-Registry.md)

# Secrets Engine Hardening v1

This document freezes hardening goals for engine internals.

Planned v1 hardening:
- Minimize secret lifetime in memory.
- Add explicit wipe support for wrapped secret values.
- Keep log and repr redaction strict.
- Preserve encrypted store v1 compatibility.

Contract notes:
- `secrets_events.v1.json` schema is frozen.
- Store v1 header magic/version are frozen.
- Fail-closed behavior remains mandatory.

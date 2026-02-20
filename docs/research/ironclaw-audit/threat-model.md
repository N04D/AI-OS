# Threat Model (STRIDE-lite)

Scope focus: tool abuse, credential leakage, and network exfiltration across Supervisor/Executor boundaries.

## Top 10 Attacks

| # | Attack | STRIDE Class | IronClaw Mitigations (evidence) | AI-OS Proposed Mitigations |
|---|---|---|---|---|
| 1 | Prompt injection -> tool abuse -> exfil | Tampering / Information Disclosure | Prompt sanitizer + safety policy (`src/safety/sanitizer.rs:1`, `src/safety/policy.rs:92`), capability checks (`src/tools/wasm/host.rs:255`) | Policy-level tool capability schema + severity `block/review`; supervisor must reject tool plan that requests undeclared capabilities |
| 2 | Malicious tool/plugin requests unauthorized egress | Elevation / Info Disclosure | Allowlist validation (`src/tools/wasm/allowlist.rs:95`), proxy deny decisions (`src/sandbox/proxy/policy.rs:122`) | Mandatory allowlist-first schema (`network-egress.schema.json`), fail-closed on missing rule |
| 3 | Secrets leakage via logs | Information Disclosure | Leak scrubbing before SSE broadcast (`src/channels/web/log_layer.rs:66`) | Standardize `secret.use` + redaction policy in supervisor artifacts; block publishing unredacted logs |
| 4 | DNS rebinding/network pivot | Tampering / Info Disclosure | Reject private/internal IP after DNS resolution (`src/tools/wasm/wrapper.rs:1008`, `src/tools/wasm/wrapper.rs:1054`) | Executor adapter must enforce `private_ip_mode=deny` and emit `policy.violation` events |
| 5 | Policy misconfiguration leading to allow-all | Tampering / Elevation | Explicit `AllowAllDecider` exists (`src/sandbox/proxy/policy.rs:164`) | Kernel schema disallows `allow_all` in strict mode; supervisor blocks policy that enables universal egress |
| 6 | Supply-chain attack on extension artifact | Tampering | SHA-256 verification before install (`src/registry/installer.rs:211`, `src/registry/installer.rs:217`) | Require pinned digest + trusted source metadata in policy for any dynamic extension activation |
| 7 | Tool tries to read/use secrets directly | Elevation / Info Disclosure | Secrets capability only checks existence (`src/tools/wasm/capabilities.rs:11`, `src/tools/wasm/host.rs:236`) | Maintain hard boundary: no plaintext secret API to tool runtime; only alias-based injection contract |
| 8 | Resource exhaustion via tool loops or large responses | DoS | Fuel/memory/time limits (`src/tools/wasm/limits.rs:9`, `src/tools/wasm/wrapper.rs:578`), response size limits (`src/tools/wasm/wrapper.rs:310`) | Executor hard caps in policy; supervisor rejects tasks requiring out-of-budget limits |
| 9 | Dynamic tool shadows trusted built-in tool | Spoofing / Elevation | Protected built-in names and rejection (`src/tools/registry.rs:33`, `src/tools/registry.rs:90`) | Add reserved namespace policy list; fail PR if protected names are overridden |
| 10 | Unauthorized/opaque secret use without audit | Repudiation | Secret usage audit records (`migrations/V2__wasm_secure_api.sql:229`), runtime record call (`src/orchestrator/api.rs:407`) | Required event types (`secret.use`, `tool.exec`, `net.req`) persisted to governance artifacts or DB sink |

## Notes on Required Scenarios
- Included explicitly: prompt injection chain (#1), malicious plugin/tool (#2), secrets in logs (#3), network pivot (#4), misconfig allow-all (#5), supply-chain attack (#6).

## Residual Risks
- MCP remote integrations use direct HTTP client flow and broaden trust surface (`src/tools/mcp/client.rs:174`).
- `UNVERIFIED`: formal AI-OS event sink architecture (artifact-only vs DB-backed) is not finalized.

## Suggested Security Invariants for AI-OS
1. Missing policy -> deny execution.
2. Missing capability declaration -> deny tool/network call.
3. Secret plaintext never enters tool process memory.
4. Every tool/network/secret event produces an auditable record.
5. Policy hash drift at runtime triggers immediate supervisor halt.

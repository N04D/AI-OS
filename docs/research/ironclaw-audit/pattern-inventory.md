# Security Pattern Inventory

Legend:
- AI-OS Placement: `Kernel` (governance constitution), `Supervisor` (evaluation/enforcement), `Executor` (runtime isolation/IO), `Userland` (optional extension surface)
- Determinism impact: `None`, `Low`, `Med`, `High`

| IronClaw Feature | Evidence (file paths + lines) | Abstract Pattern | Threats Addressed | AI-OS Placement (Kernel / Supervisor / Executor / Userland) | Determinism impact | Recommended Adoption | Notes / Required Changes |
|---|---|---|---|---|---|---|---|
| WASM capability model (deny by default) | `src/tools/wasm/capabilities.rs:4`, `src/tools/wasm/capabilities.rs:23`, `src/tools/wasm/host.rs:4` Quote: "All capabilities are opt-in; tools have NO access by default." | Explicit capability grant model with default-deny | Tool abuse, privilege escalation | Kernel + Supervisor + Executor | Low | Yes | Encode as versioned policy schema, enforced pre-dispatch and at runtime |
| HTTP allowlist with host/path/method gates | `src/tools/wasm/allowlist.rs:3`, `src/tools/wasm/allowlist.rs:113`, `src/tools/wasm/wrapper.rs:268` Quote: "Check HTTP allowlist" | Structured egress policy with fine-grained endpoint matching | SSRF, data exfiltration, rogue API calls | Kernel + Executor | Low | Yes | Keep allowlist-first; prohibit implicit wildcards by policy severity |
| DNS rebinding/private-IP rejection | `src/tools/wasm/wrapper.rs:319`, `src/tools/wasm/wrapper.rs:1008`, `src/tools/wasm/wrapper.rs:1056` Quote: "DNS rebinding detected" | Post-allowlist DNS/IP safety verification | DNS rebinding, network pivot to internal services | Executor | Low | Yes | Add mandatory `private_ip_mode=deny` in egress schema |
| Secret boundary + host-side injection | `src/tools/wasm/wrapper.rs:72`, `src/tools/wasm/wrapper.rs:653`, `migrations/V2__wasm_secure_api.sql:92` Quote: "WASM tools NEVER see plaintext secrets" | Secrets only decrypted at trusted boundary; injected just-in-time | Secret exfiltration from untrusted code | Kernel + Executor | Low | Yes | AI-OS should expose secret aliases only; no plaintext in tool context |
| Encrypted secret storage (AES-GCM + HKDF) | `src/secrets/crypto.rs:3`, `src/secrets/crypto.rs:8`, `src/secrets/crypto.rs:128` Quote: "Uses AES-256-GCM" | Envelope-style secret crypto with per-secret derivation | At-rest secret compromise risk | Executor / infra | None | Experimental | AI-OS currently Git-ledger oriented; storage backend decision still UNVERIFIED |
| Leak detection on request/response/log boundaries | `src/safety/leak_detector.rs:9`, `src/safety/leak_detector.rs:291`, `src/channels/web/log_layer.rs:66` Quote: "Leak detection happens at TWO points" | Boundary DLP scanner with block/redact/warn actions | Secret leakage via outputs/logs | Supervisor + Executor | Med | Yes | Keep deterministic pattern sets versioned in policy files |
| Policy action/severity model | `src/safety/policy.rs:7`, `src/safety/policy.rs:81`, `src/safety/policy.rs:86` Quote: "Action to take when a policy is violated" | Severity-to-action decision ladder | Prompt injection, malicious content flow | Kernel + Supervisor | Low | Yes | Map to AI-OS levels: `block/warn/review/allow` |
| Prompt-injection sanitizer | `src/safety/sanitizer.rs:1`, `src/safety/sanitizer.rs:60`, `src/safety/sanitizer.rs:233` Quote: "Sanitizer for detecting and neutralizing prompt injection attempts." | Pre-processing sanitizer for untrusted text | Prompt injection, role hijack | Executor + Userland | Med | Experimental | Risk of false positives; require policy toggle and audit mode |
| Resource limits (memory/fuel/timeout) | `src/tools/wasm/limits.rs:9`, `src/tools/wasm/runtime.rs:107`, `src/tools/wasm/wrapper.rs:578` Quote: "Default memory limit: 10 MB" | Multi-axis compute bounding for untrusted tasks | DoS/resource exhaustion | Executor | Low | Yes | Include hard caps in executor contract and policy schema |
| Container sandbox with proxied network | `src/sandbox/manager.rs:163`, `src/sandbox/container.rs:231`, `src/sandbox/config.rs:52` Quote: "Proxied (allowlist only)" | Isolated process execution + central egress control point | Host compromise, unrestricted outbound traffic | Executor | Med | Experimental | Keep optional in AI-OS; avoid architecture drift into full job platform |
| Secret usage / leak event audit trails | `migrations/V2__wasm_secure_api.sql:227`, `migrations/V2__wasm_secure_api.sql:258`, `src/orchestrator/api.rs:407` Quote: "Record usage for audit trail" | Evented audit records for secret access and leak actions | Non-repudiation gaps, forensic blind spots | Supervisor + Executor | Low | Yes | AI-OS should emit deterministic JSON artifacts and optionally DB sink |
| Supply-chain checks for downloaded extensions (SHA-256) | `src/registry/installer.rs:211`, `src/registry/installer.rs:217`, `src/registry/manifest.rs:93` Quote: "SHA256 mismatch" | Artifact integrity verification before activation | Tampered extension binary | Supervisor + Userland | None | Yes | Add policy gate for trusted source + hash pinning |
| Built-in tool shadow protection | `src/tools/registry.rs:33`, `src/tools/registry.rs:90`, `src/tools/registry.rs:94` Quote: "Rejected tool registration: would shadow a built-in tool" | Namespace protection for security-critical built-ins | Malicious override of trusted tools | Supervisor + Executor | None | Yes | Add immutable reserved-tool list in policy |
| MCP remote client pathway | `src/tools/mcp/client.rs:174`, `src/tools/mcp/config.rs:78`, `src/tools/mcp/client.rs:193` Quote: "Remote MCP servers must use HTTPS" | External tool-protocol bridge with direct HTTP transport | Exfil to third-party services, trust sprawl | Userland | High | Experimental | Keep outside kernel; require explicit opt-in and strict egress policy adapters |

## AI-OS Fit Map Summary
- Move to `Kernel` policy: capabilities contract, egress contract, secret boundary contract, severity/actions, reserved-tool names.
- Move to `Supervisor`: deterministic policy evaluation + violation artifacts + release gating.
- Move to `Executor`: runtime enforcement (allowlist, rebinding checks, limits, credential injection boundary).
- Keep in `Userland` only: MCP federation, dynamic extension ecosystems, rich auth UX.

## Incompatibilities / Drift Risks
- Full IronClaw job orchestration stack (orchestrator + worker + DB event platform) would exceed AI-OS current governance-first kernel scope.
- Large runtime statefulness conflicts with AI-OS doctrine "no hidden state" unless made reconstructable and policy-versioned.


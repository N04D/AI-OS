# Trust Boundaries

## Zones
- `Z0 Kernel/Policy Boundary` (AI-OS governance constitution)
  - Evidence AI-OS: `docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:65`, `docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:100`
- `Z1 Supervisor Boundary` (policy load/evaluate/enforce)
  - Evidence AI-OS: `supervisor/pr_gate/policy_loader.py:23`, `supervisor/supervisor.py:135`
- `Z2 Executor Boundary` (tool runtime, sandbox, egress controls)
  - Evidence IronClaw: `src/tools/wasm/host.rs:17`, `src/tools/wasm/wrapper.rs:268`, `src/sandbox/manager.rs:163`
- `Z3 Tool Boundary` (untrusted WASM or external tool servers)
  - Evidence IronClaw: `src/tools/wasm/wrapper.rs:72`, `src/tools/mcp/client.rs:25`
- `Z4 Network Boundary` (proxy/allowlist and external services)
  - Evidence IronClaw: `src/sandbox/proxy/policy.rs:122`, `src/sandbox/proxy/http.rs:225`
- `Z5 Secrets Boundary` (encrypted storage + on-demand decrypt/inject)
  - Evidence IronClaw: `src/secrets/crypto.rs:3`, `src/orchestrator/api.rs:396`
- `Z6 Storage/Audit Boundary` (event logs, artifacts, optional DB)
  - Evidence IronClaw: `migrations/V2__wasm_secure_api.sql:229`, `src/history/store.rs:773`
  - Evidence AI-OS: `artifacts/governance/*` via `supervisor/supervisor.py:126`

## Text Diagram
```text
[Z0 Kernel Policy]
   |  policy hash + schemas
   v
[Z1 Supervisor] --enforcement decisions--> [Z6 Audit Artifacts]
   | dispatch contract
   v
[Z2 Executor Runtime] --capability gates--> [Z3 Tools (untrusted)]
   | egress decision / credential injection
   v
[Z4 Network Boundary] ---------------------> [External Services]
   ^
   | secret resolution
[Z5 Secrets Boundary]
```

## Cross-Boundary Data Flows
1. `Policy load`: Z0 -> Z1
- Data: policy YAML + hash
- Guard: hash-validation and lockdown checks (`supervisor/pr_gate/policy_loader.py:46`, `supervisor/supervisor.py:138`)

2. `Tool invocation`: Z1 -> Z2 -> Z3
- Data: tool name, params, capability context
- Guard: default-deny capability checks (`src/tools/wasm/capabilities.rs:4`, `src/tools/wasm/host.rs:255`)

3. `Network egress`: Z3 -> Z4 -> external
- Data: method/url/headers/body
- Guard: allowlist + rebinding/private IP reject (`src/tools/wasm/wrapper.rs:268`, `src/tools/wasm/wrapper.rs:320`, `src/tools/wasm/wrapper.rs:1056`)

4. `Secrets use`: Z5 -> Z2/Z4 (never Z3 plaintext)
- Data: decrypted secret only in trusted host boundary
- Guard: host injection model (`src/tools/wasm/wrapper.rs:72`, `migrations/V2__wasm_secure_api.sql:92`)

5. `Audit/provenance`: Z2/Z4/Z5 -> Z6
- Data: secret usage events, leak events, job events
- Guard: append-only event records (schema-level) (`migrations/V2__wasm_secure_api.sql:229`, `migrations/V2__wasm_secure_api.sql:258`, `src/history/store.rs:783`)

## Boundary Notes
- MCP pathways can bypass strict in-process sandbox assumptions; treat as separate `Userland` trust class.
- `UNVERIFIED`: exact final AI-OS executor topology for network chokepoints is not yet codified in this repo.

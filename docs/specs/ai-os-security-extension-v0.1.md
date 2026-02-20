# AI-OS Security Extension v0.1

STATUS: Experimental – Not production-ready – Architectural exploration.
Version: v0.1
Type: Governance + Runtime interface spec (no implementation)

## 1. Objectives
- Define a deterministic capability model for AI-OS tool/runtime execution.
- Define fail-closed security policy semantics for supervisor enforcement.
- Define secret boundary contract where untrusted tools never access plaintext secrets.
- Define network egress policy with allowlist-first behavior.
- Define auditable event taxonomy for security-relevant actions.

## 2. Non-goals
- No direct import of IronClaw runtime architecture.
- No database migration requirements in this spec.
- No replacement of existing PR governance policy engine.
- No mandate to adopt MCP federation as a kernel feature.

## 3. Background Evidence
- Deny-by-default capability model exists in IronClaw (`src/tools/wasm/capabilities.rs:4`).
- AI-OS governance requires fail-closed + hash-validated policy (`docs/architecture/ARCHITECTURE_CHARTER_v1.0.md:124`, `supervisor/pr_gate/policy_loader.py:46`).

## 4. Capability Model (Conceptual)
Capability domains:
- `workspace.read`
- `http.request`
- `tool.invoke`
- `secret.presence`
- `secret.inject` (host-only action; never exposed to untrusted tool code)

Rules:
- All capabilities are denied by default.
- Capability grants must be explicit in versioned policy.
- Supervisor validates requested capabilities against task intent and policy.
- Executor enforces runtime checks before side effects.

## 5. Policy Severity Levels
Security policy decision levels:
- `block`: deny action and emit violation event.
- `warn`: allow action, record warning event.
- `review`: pause for governed/human or higher-trust supervisor decision.
- `allow`: action proceeds with audit event.

Fail-closed behavior:
- Unknown action type or missing policy rule -> `block`.
- Schema validation failure -> `block`.

## 6. Secrets Boundary Contract
Contract requirements:
- Tools may only reference secret aliases (names/handles), never raw values.
- Secret decryption/injection occurs only at trusted host boundary.
- Secrets may be injected into headers/query/path per policy mapping.
- Secret values must be redacted in logs/errors/events.
- Every successful or denied secret injection attempt emits `secret.use`.

## 7. Network Egress Policy
Policy posture: allowlist-first.

Requirements:
- Allowed endpoint constraints include host, path prefix, and method.
- HTTPS required by default.
- URL userinfo (`user:pass@`) denied.
- DNS rebinding and private IP targets denied.
- Max request/response size and timeout governed by policy.

## 8. Audit Event Types
Required normalized event types:
- `tool.exec` - tool execution attempt/result.
- `net.req` - outbound network request decision/result.
- `secret.use` - secret resolution/injection decision/result.
- `policy.violation` - blocked or review-required rule violation.

Minimum event fields:
- `event_id`, `timestamp`, `policy_version`, `policy_hash`, `actor`, `resource`, `decision`, `reason`, `correlation_id`.

## 9. Integration Points
`Supervisor` interface (conceptual):
- `evaluate_security_policy(action_context) -> decision`
- `validate_policy_hash(expected_hash) -> ok|error`
- `publish_security_status(event)`

`Executor` interface (conceptual):
- `enforce_capability(request, policy) -> allow|deny`
- `enforce_network_egress(request, policy) -> allow|deny`
- `resolve_and_inject_secret(mapping, context) -> injected|denied`
- `emit_audit_event(event)`

## 10. Determinism Constraints
- Same policy version + same policy hash + same normalized inputs => same decision.
- Policy cannot mutate during execution window.
- Security decisions must be replayable from recorded events/artifacts.

## 11. Compatibility Notes
- Compatible with existing AI-OS policy hashing and lockdown (`supervisor/supervisor.py:135`).
- Dynamic plugin ecosystems remain userland unless governance requirements are met.

## 12. Open Questions
- `UNVERIFIED`: canonical long-term event sink for AI-OS (`artifact JSON` only vs optional DB mirror).
- `UNVERIFIED`: exact executor plugin API shape for non-Python runtimes.

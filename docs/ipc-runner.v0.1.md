# IPC Runner v0.1

## Scope
Defines the code-enforced plugin IPC contract for Milestone 2 Phase 4B.
This phase provides secure runtime invocation only for resolved enabled plugins.

## Transport
- stdin/stdout NDJSON
- Exactly one JSON object per line
- UTF-8 encoding

## Request Contract
Each request line must decode to a JSON object with:
- `type`: must equal `"request"`
- `id`: string
- `method`: string
- `payload`: object

## Response Contract
Each response line must decode to a JSON object with:
- `type`: must equal `"response"`
- `id`: string
- `ok`: boolean
- `result`: object or `null`
- `error`: object or `null`

## Hard Limits (Code-Enforced)
- Max request line bytes: `1_000_000`
- Max response line bytes: `1_000_000`

If either limit is exceeded, execution fails closed and plugin process is terminated.
This includes partial stdout with no newline: buffered bytes are capped and terminated
with `RESPONSE_TOO_LARGE` once the limit is crossed.

## Timeout
- Per-request timeout is loaded from plugin manifest/runtime descriptor.
- `runtime.timeout_seconds` must be present and > 0.
- Missing/invalid timeout => deny.

## Failure Rules (Fail-Closed)
- Invalid JSON from plugin => kill plugin and return structured failure.
- Missing required response fields => kill plugin and return structured failure.
- Timeout => kill plugin and return structured failure.
- Plugin crash/broken pipe => mark unhealthy and return structured failure.
- Oversized request or response line => kill plugin and return structured failure.

## Audit Ordering Guarantees
For each request flow, audit events are emitted before returning:
- `spawn_attempt` (if spawn needed)
- `spawn` (success/failure)
- `request_start`
- `request`
- `kill` (if termination occurs)
- `timeout` (on timeout path)
- `response`
- `request_end` (final outcome)
- `disable/refuse` (policy/safety refusals)

If audit writing fails, execution fails closed with `AUDIT_LOG_WRITE_FAILED`.
Runner refuses to execute/spawn/send when audit sink is unavailable.

## Unhealthy Threshold
- Failures increment in-memory failure count on:
  - timeout
  - invalid JSON response
  - broken pipe
  - crash
  - response too large
  - invalid response schema
- Success resets the failure counter for that plugin.
- After `N` failures (`N=3` default), plugin is marked unhealthy and further requests
  are refused with `PLUGIN_UNHEALTHY` for the runner instance.

## Security Invariants
- No shell execution (`shell=False` only).
- No parent environment inheritance (empty base env + allowlist only).
- No network calls inside runner implementation.
- No automatic enabling.
- Only discovered + effectively enabled plugins can run.

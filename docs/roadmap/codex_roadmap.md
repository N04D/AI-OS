# 🧱 FASE A — Engine Freeze & Hardening

---
# Secrets A → B Execution Roadmap

Status: ACTIVE BUILD1

Owner: Codex
Rule: Each checkbox may only be checked when:
- Code is implemented
- Tests are added
- pytest passes
- No regressions

---

## PHASE A — ENGINE FREEZE

### PR-00 Freeze Contracts

- [x] Add secrets_events.v1.json to docs/specs
- [x] Add secrets_store_format.v1.md
- [x] Add secrets_policy_context.v1.md
- [x] Add secrets_rate_limits_anomaly.v1.md
- [x] Add secrets_eventbus_adapter.v1.md
- [x] Add secrets_context_factory.v1.md
- [x] Add secrets_engine_hardening.v1.md
- [x] Add test asserting event schema version constant
- [x] Add test asserting store header magic "AIOSSEC1"
- [x] All tests pass

---

### PR-01 EventBus Adapter

- [x] Implement EventSink interface
- [x] Implement MultiplexerSink
- [x] Implement SupervisorEventSink (file mode)
- [x] Add failure handling (EVENTBUS_EMIT_FAILED)
- [x] Add fan-out test
- [x] Validate emitted events against schema
- [x] All tests pass

---

### PR-02 ContextFactory Enforcement

- [x] Implement ContextFactory
- [x] Remove all raw string contexts
- [x] Enforce context required in SecretsManager
- [x] Add unknown-context deny test
- [x] Add trust-level validation test
- [x] Add elevated-context test
- [x] All tests pass

---

### PR-03 Rate Limits + Anomaly

- [x] Implement fixed-window rate limiter
- [x] Enforce per classification limits
- [x] Emit RATE_LIMIT_EXCEEDED
- [x] Emit anomaly signals
- [x] Add limit exceed test
- [x] Add window reset test
- [x] Add anomaly spike test
- [x] All tests pass

---

### PR-04 Engine Hardening

- [x] Refactor SecretValue to bytearray storage
- [x] Implement wipe()
- [x] Implement context manager support
- [x] Redacted __repr__
- [x] Optional core dump disable (Unix)
- [x] Add wipe test
- [x] Add no-log-leak test
- [x] Add concurrent write safety test
- [x] All tests pass

---

## PHASE B — GOVERNANCE INTEGRATION

### PR-05 BudgetSink (Observe Mode)

- [x] Implement BudgetChargeSink
- [x] Map classification to cost
- [x] Emit secret.budget.charge events
- [x] Add observe mode flag
- [x] Add telemetry test
- [x] All tests pass

---

### PR-06 Budget Enforcement

- [ ] Implement BudgetGate wrapper
- [ ] Add feature flag (off|observe|enforce)
- [ ] Deny with BUDGET_EXCEEDED
- [ ] Add enforcement test
- [ ] All tests pass

---

### PR-07 Cross-Agent Quota

- [ ] Implement quota per agent_id + epoch
- [ ] Add quota exceed test
- [ ] Ensure agent isolation
- [ ] All tests pass

---

### PR-08 Approval Tokens (CRITICAL)

- [ ] Require approval token for CRITICAL secrets
- [ ] Implement token validation
- [ ] Add missing-token deny test
- [ ] Add valid-token allow test
- [ ] All tests pass

---

### PR-09 Kill Switch

- [ ] Implement context suspension mechanism
- [ ] Add anomaly-triggered suspension
- [ ] Add manual unlock
- [ ] Add suspension test
- [ ] All tests pass

---

## FINAL VERIFICATION

- [ ] No secret values appear in logs (grep test)
- [ ] Store v1 readable
- [ ] Event schema unchanged
- [ ] All tests pass1
- [ ] Feature flags documented

---

END STATE:

Secrets subsystem is:
- Cryptographically secure
- Capability controlled
- Rate limited
- Budget enforced
- Governance integrated
- Engine stable

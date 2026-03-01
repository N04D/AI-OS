# Skills Mediation Layer v0.1

## Purpose
The Skills Mediation Layer sits above `kernel.dispatch` and enforces deny-by-default authorization for external channels before any plugin method invocation.

Flow:

`channel ingress -> skills policy -> dispatch -> runner -> plugin`

## Threat Model
This layer is designed to mitigate:
- direct channel-to-plugin method access bypassing authorization,
- unauthorized users invoking sensitive plugin methods,
- accidental or malicious invocation of undefined or unsafe operations,
- malformed input payloads that bypass expected schema checks.

## Deny-By-Default Principle
Policy sets:
- `default_decision: deny`

Requests are denied unless all checks pass:
1. policy file is present and valid,
2. channel exists in policy,
3. user ID is allowed for that channel,
4. skill ID is allowed for that channel,
5. skill exists and maps to a concrete `(plugin_id, method)`,
6. payload passes minimal schema checks,
7. scope/rate/quota hardening checks pass.

If any check fails, the result is fail-closed.

## Policy File
Canonical policy path:
- `governance/policy/skills/skills.v0.1.yaml`

Example:

```yaml
version: "0.1"
default_decision: "deny"
skills:
  send-message:
    description: "Send message through notifier"
    target:
      plugin_id: "notifier-telegram"
      method: "notify"
    input_schema:
      type: "object"
      required: ["text", "recipient"]
      properties:
        text:
          type: "string"
        recipient:
          type: "string"
    safe_defaults:
      priority: "normal"
    rate_limit:
      cooldown_seconds: 10
    allowed_recipients:
      - "alerts-room"
      - "ops-room"
channels:
  telegram:
    allowed_users:
      - "111"
    allowed_skills:
      - "send-message"
    quotas:
      per_user_per_hour: 30
```

## Channel Integration
Channels should call:

```python
from kernel.skills import run_skill

result = run_skill(
    channel_id="telegram",
    user_id="111",
    skill_id="send-message",
    payload={"text": "hello", "recipient": "alerts-room"},
    policy_path="governance/policy/skills/skills.v0.1.yaml",
    registry_path="state/plugins/registry.json",
    config_path="state/plugins/config.json",
    audit_log_path="logs/control/skills.jsonl",
)
```

Do not call `dispatch()` directly from external ingress once skills mediation is enabled.

## Hardening v0.2
v0.2 adds deterministic fail-closed hardening controls inside `run_skill()` in this order:
1. Basic allow checks (channel/user/skill)
2. Payload validation
3. Scope enforcement (`allowed_recipients`)
4. Cooldown enforcement (`rate_limit.cooldown_seconds`)
5. Quota enforcement (`channels.<id>.quotas.per_user_per_hour`)
6. Dispatch

### Cooldown
- Configured per skill.
- Keyed by `(user_id, skill_id)`.
- If a user repeats before cooldown elapses: `SKILL_RATE_LIMITED`.
- Cooldown state is updated only after successful dispatch (`result.ok == true`).

### Quota
- Configured per channel with `per_user_per_hour`.
- Sliding one-hour window per user.
- If limit reached: `SKILL_QUOTA_EXCEEDED`.

### Scope Enforcement
- If `allowed_recipients` is configured, payload recipient must be in that list.
- Violations return: `SKILL_SCOPE_VIOLATION`.

### Storage Model
- v0.2 cooldown/quota counters are in-memory only.
- Restart clears counters.
- Future versions may add persisted counters for continuity across restarts.

## Safe Skill Addition Checklist
1. Add a new `skill_id` matching `^[a-z0-9-]+$`.
2. Map to an existing plugin and method already gated by dispatch/method policy.
3. Define strict `input_schema` (`type: object`, required fields, property types).
4. Add channel permission entries with explicit `allowed_users` and `allowed_skills`.
5. For risky actions, define `allowed_recipients`, `rate_limit`, and channel `quotas`.
6. Run tests:
   - `python -m unittest -v tests.test_skills_policy`

## Explicit Security Restriction
Kernel rebuild and privileged operations are forbidden via skills.

Skills must never be used to expose:
- kernel rebuild paths,
- privileged host operations,
- arbitrary command execution,
- governance mutation or policy bypass.

## Output Contract
Success:

```json
{
  "ok": true,
  "skill_id": "send-message",
  "result": {"ok": true}
}
```

Deny:

```json
{
  "ok": false,
  "skill_id": "send-message",
  "error": {
    "code": "SKILL_SCOPE_VIOLATION",
    "details": ["recipient_not_allowed"]
  }
}
```

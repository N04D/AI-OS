# Secrets ContextFactory v1

ContextFactory will provide typed construction of policy contexts.

Planned behavior:
- Replace free-form context strings.
- Validate known context IDs.
- Carry trust-level metadata for policy decisions.

Contract notes:
- Unknown context must fail-closed.
- Context serialization must not include secret values.

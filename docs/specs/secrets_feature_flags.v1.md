# Secrets Feature Flags v1

The secrets subsystem supports these runtime flags on `SecretsManager`:

- `budget_mode`: `off|observe|enforce`
- `observe_budget_charges`: compatibility flag that maps to `budget_mode=observe` when `budget_mode` is not explicitly set
- `disable_core_dumps`: best-effort Unix core-dump disable at manager init
- `auto_suspend_on_anomaly`: enables kill-switch suspension when anomaly conditions are detected by rate limiting

Operational notes:
- `budget_mode=off`: no budget charge or enforcement behavior.
- `budget_mode=observe`: emits budget telemetry events only.
- `budget_mode=enforce`: emits telemetry and denies when budget gate returns `BUDGET_EXCEEDED`.
- `auto_suspend_on_anomaly=false` by default to avoid unintended lockouts.

# autonomy_budget_gate Redundancy Proof

Date: 2026-02-27
Scope: `supervisor/autonomy_budget_gate.py`

## 1) Dependency scan (runtime codepaths)

Command:

```bash
rg -n "from supervisor\.autonomy_budget_gate|import supervisor\.autonomy_budget_gate|autonomy_budget_gate\." \
  supervisor orchestrator autonomy_orchestrator executor scripts
```

Result:

- No runtime references found.
- Only test/docs/codex notes still referenced the module name.

## 2) Runtime behavior source-of-truth

Current runtime path:

- `supervisor/night_executor.py` budget checks now route through `supervisor.autonomy_budget`.
- No production import of `supervisor.autonomy_budget_gate` remains.

## 3) Compatibility behavior check

Command:

```bash
python3 - <<'PY'
import json, tempfile
from supervisor import autonomy_budget_gate as gate
from supervisor import autonomy_budget as base

actions=['promotion','intake','materialize','exec_attempt','commit']
out=[]
ts=1704067200
for a in actions:
    with tempfile.TemporaryDirectory() as dg, tempfile.TemporaryDirectory() as db:
        gp=gate.check_and_consume(a, now_epoch_s=ts, host_state_dir=dg)
        bp=base.consume_budget(a, now_epoch_s=ts, host_state_dir=db)
        out.append({
            'action':a,
            'allowed_equivalent': gp.get('allowed') == bp.get('consumed'),
            'gate_allowed':gp.get('allowed'),
            'base_consumed':bp.get('consumed'),
        })
print(json.dumps(out, indent=2, sort_keys=True))
PY
```

Observed:

- `allowed_equivalent` was `true` for all actions.
- This confirms `autonomy_budget_gate` is a compatibility layer, not a unique runtime dependency.

## Conclusion

`supervisor/autonomy_budget_gate.py` is verified unused in production/runtime codepaths and is safe to remove in a separate change set.

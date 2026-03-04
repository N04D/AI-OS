# Memory Layout

This folder stores persistent working memory for fast recovery after reboot, reconnect, or host migration.

## Structure
- `context.md`: global rules and behavior contract.
- `backlog.md`: long-lived issues and investigations.
- `decisions.md`: irreversible decisions and rationale.
- `sessions/`: historical session logs.
- `current/`: what is active now.
- `infra/`: machine and environment facts.
- `runbooks/`: copy-paste operational procedures.
- `handover/`: operator-to-agent and agent-to-operator transfer notes.
- `templates/`: templates for consistent updates.

## Update cadence
- Update `current/now.md` at start and end of every work block.
- Update `infra/system_snapshot.md` after major system changes.
- Add one line to `handover/next_steps.md` when stopping.

## Minimum recovery set
If time is limited, read in this order:
1. `context.md`
2. `current/now.md`
3. `handover/next_steps.md`
4. `backlog.md`

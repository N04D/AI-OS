# Local-First Git Workflow v0.1

Doel:
- Eerst lokaal valideren en mergen op Gitea.
- Pas daarna optioneel mirroren/pushen naar GitHub.

## Remote conventie

- `origin` = lokale Gitea (bron van waarheid)
- `github` = externe mirror

## Standaard flow

1. Werk op feature branch.
2. Open PR naar `dev` op lokale Gitea.
3. Merge op lokale Gitea nadat tests/gates groen zijn.
4. Sync lokale `dev`.
5. Publiceer optioneel naar GitHub via:

```bash
scripts/publish_github_after_local_gate.sh --branch dev
```

Dit script blokkeert publish als:
- working tree niet schoon is
- `HEAD` nog niet op `origin/dev` staat
- lokale test harness faalt

# Agent Workspace Manager v0.1

Status: draft  
Scope: per-agent isolated workspace orchestration for governed development flows

## Objective

Provide deterministic, user-agnostic workspace isolation per agent:

- Workspace root: `/var/lib/aios/agents/<agent>/`
- Layout:
  - `repo/` cloned repository
  - `env/` local overlays (ignored)
  - `logs/` runtime logs (ignored)

No secrets are committed. Runtime overlays stay outside repository history.

## CLI

Commands:

- `./scripts/aiosctl agent workspace sync --agent <name>`
- `./scripts/aiosctl agent workspace run-tests --agent <name>`
- `./scripts/aiosctl agent workspace create-branch --agent <name> --name <branch>`
- `./scripts/aiosctl agent workspace push-pr --agent <name> --title <title> --body <body>`

Optional:

- `--root <path>` override workspace root for testing/operator control.
- `--base-branch <name>` for `sync` and `push-pr`.

## Determinism and Pathing

- Default workspace root resolves to `/var/lib/aios/agents`.
- Override may be supplied via `AIOS_AGENT_WORKSPACE_ROOT` or CLI `--root`.
- No absolute user-home assumptions are used in manager logic.

## Email-Ready Runtime Overlay

- Workspace runtime env file:
  - `AIOS_ENV_FILE=<workspace>/env/.env.runtime`
- `run-tests` exports `AIOS_ENV_FILE` to isolate runtime credentials and channel settings.
- Default behavior remains test-first; network-dependent integrations are expected to be mocked in tests.

## Governance and Safety

- Clean-worktree guard enforced before:
  - `create-branch`
  - `push-pr`
- `push-pr` requires:
  - `GITEA_TOKEN`
  - `GITEA_BASE_URL`
- PR creation is deterministic on:
  - current branch
  - explicit `title`, `body`, `base`

## Expected Artifacts

- Workspace-level `.gitignore` under `<workspace>/.gitignore`:
  - `env/`
  - `logs/`
- No workspace runtime overlays are staged from repository root.

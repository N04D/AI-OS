# Vault Alignment

## Canonical Root

- expected vault root: `/data/srv/aios/AI-OS`
- terminal working tree: `/data/srv/aios/AI-OS`
- canonical git branch: `feature/console-readline-v0.1`

## Clone Detection

Detected AI-OS clones:

- `/data/srv/aios/AI-OS`
  - HEAD: `ba7da61496f3d20a25548f064531e267315a4262`
  - branch: `feature/console-readline-v0.1`
  - `config/remote_sources.yaml`: present
- `/data/home/infra/night/AI-OS`
  - HEAD: `e0d93316d9ba58e17c514ed17a80bf7ea99995ea`
  - branch: `dev`
  - `config/remote_sources.yaml`: missing

## Obsidian Target

- launcher: `/home/n04d/.local/bin/obsidian-aios`
- canonical launch path: `/data/srv/aios/AI-OS`
- desktop symlink: `/home/n04d/Desktop/AI-OS -> /data/srv/aios/AI-OS`

## Root Structure Check

Required folders at canonical root:

- `docs/`: present
- `docs/specs/`: present
- `docs/roadmap/`: present
- `docs/adr/`: present
- `config/`: present

Consistency checks:

- specs outside docs root (`spec/`, `specs/`): not present
- roadmap files outside `docs/roadmap/`: none tracked
- ADR files outside `docs/adr/`: none tracked

Conclusion: Obsidian and terminal are aligned to the canonical repository root.

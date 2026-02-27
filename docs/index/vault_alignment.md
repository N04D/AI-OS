# Vault Alignment

- expected vault root: /data/srv/aios/AI-OS
- required folders visible at root:
  - docs: present
  - docs/specs: present
  - docs/archive/legacy_specs: present
  - docs/roadmap: present
  - docs/adr: present
  - config: present

## Structural Checks
- spec/ exists at repo root: False
- specs/ exists at repo root: False
- roadmap files outside docs/roadmap (tracked): none
- ADR files outside docs/adr (tracked): none

## HEAD Alignment
- canonical structure matches git HEAD for moved/archived paths in this phase: yes

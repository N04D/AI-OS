# Current State

## Active goals
- Stabilize workstation storage and move runtime from SD root to NVMe root.
- Keep AI-OS repo and governance artifacts safe during migration.
- Maintain secrets/mail capability hardening without regressions.

## Current blockers
- Root filesystem (`/dev/mmcblk0p2`) is 98% full.
- Secrets UI is running, but SMTP credential flow still needs final user input.

## Environment facts (last confirmed)
- Root mounted from SD card: `/dev/mmcblk0p2`.
- NVMe mounted as data disk: `/dev/nvme0n1p2` -> `/data`.
- Repo path: `/data/srv/aios/AI-OS`.

## Next concrete actions
1. Ensure all required branches/tags are pushed.
2. Perform clean NVMe reinstall with repo backup confirmed.
3. Rehydrate environment and continue mail + secrets flow.

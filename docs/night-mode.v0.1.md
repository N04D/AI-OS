# Night Mode v0.1

Night Mode must run in a dedicated workspace, separate from daytime or interactive development trees.

## Bootstrap Requirement

Use `scripts/night-bootstrap.sh` before any Night Mode task execution.
The script ensures the Night workspace is a clean clone/reset state and that `./scripts/test-all.sh` passes in that workspace.
The bootstrap auto-detects the default branch using `origin/HEAD` instead of hardcoding `main`.
For compatibility across repositories, harness discovery supports `./scripts/test-all.sh` first and `./script/test-all.sh` as fallback.

## Fail-Closed Rule

If the working tree is dirty at preflight, Night Mode must hard stop.
No task execution or commit operations are allowed until a clean dedicated workspace is ready.

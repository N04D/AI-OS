# Night Mode v0.1

Night Mode must run in a dedicated workspace, separate from daytime or interactive development trees.

## Bootstrap Requirement

Use `scripts/night-bootstrap.sh` before any Night Mode task execution.
The script ensures the Night workspace is a clean clone/reset state and that `./scripts/test-all.sh` passes in that workspace.
Night Mode targets `dev` by default via `NIGHT_BRANCH`, and the bootstrap strictly checks out/resets `origin/$NIGHT_BRANCH`.
Example: `NIGHT_BRANCH=dev ./scripts/night-bootstrap.sh`
For compatibility across repositories, harness discovery supports `./scripts/test-all.sh` first and `./script/test-all.sh` as fallback.

## Fail-Closed Rule

If the working tree is dirty at preflight, Night Mode must hard stop.
No task execution or commit operations are allowed until a clean dedicated workspace is ready.

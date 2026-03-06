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

## Automated Night Schedule (systemd user timer)

Install a nightly run at 02:30 local time:

```bash
tools/install_night_mode_systemd.sh --on-calendar "*-*-* 02:30:00" --source local
```

Useful commands:

```bash
systemctl --user list-timers aios-night-mode.timer
systemctl --user start aios-night-mode.service
journalctl --user -u aios-night-mode.service -n 200 --no-pager
```

Set the receiver for local issue text like `Send an email to <YOUR_EMAIL> ...` in:

`~/.config/aios/night_mode.env`:

`AIOS_NIGHT_OPERATOR_EMAIL=you@example.com`

Night-kick (reactie na elke run) staat op:

`AIOS_NIGHT_KICK_SCRIPT=/home/n04d/AI-OS/tools/codex_night_kick.sh`

Morning report output (dagelijks) staat standaard op:

`workspace/codex/night/reports/YYYY-MM-DD.md`

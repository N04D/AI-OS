import os
import subprocess


def preferred_remote_name() -> str:
    env_remote = (os.environ.get("AIOS_GIT_REMOTE") or "").strip()
    if env_remote:
        return env_remote

    for candidate in ("gitea", "origin"):
        result = subprocess.run(
            ["git", "config", "--get", f"remote.{candidate}.url"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return candidate

    return "origin"


def required_remote_url() -> tuple[str, str]:
    remote_name = preferred_remote_name()
    result = subprocess.run(
        ["git", "config", "--get", f"remote.{remote_name}.url"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Could not get git remote.{remote_name}.url. Is this a git repository?")
    return remote_name, result.stdout.strip()

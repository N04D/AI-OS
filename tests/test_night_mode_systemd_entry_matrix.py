from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "tools" / "night_mode_systemd_entry.sh"


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _prepare_fake_repo(path: Path, *, with_aiosctl: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if with_aiosctl:
        _write_executable(
            path / "scripts" / "aiosctl",
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "echo '{\"status\":\"ok\",\"summary_path\":\"\"}'\n",
        )


def _run_entrypoint(fake_repo: Path, lock_path: Path, log_path: Path, *, stale_seconds: str = "21600") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "AIOS_NIGHT_REPO_ROOT": str(fake_repo),
            "AIOS_NIGHT_KICK_SCRIPT": "/bin/true",
            "AIOS_NIGHT_REPORT_VALIDATOR": "/bin/true",
            "AIOS_NIGHT_LOCK_PATH": str(lock_path),
            "AIOS_NIGHT_LOG_PATH": str(log_path),
            "AIOS_NIGHT_LOCK_STALE_SECONDS": stale_seconds,
        }
    )
    return subprocess.run(
        ["bash", str(ENTRYPOINT)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_night_mode_systemd_entry_lock_preflight_regression_matrix(tmp_path: Path) -> None:
    # success: preflight passes and run exits cleanly.
    repo_success = tmp_path / "repo-success"
    lock_success = tmp_path / "locks" / "success.lock"
    log_success = tmp_path / "logs" / "success.log"
    _prepare_fake_repo(repo_success, with_aiosctl=True)
    success = _run_entrypoint(repo_success, lock_success, log_success)
    assert success.returncode == 0, success.stderr
    assert not lock_success.exists()

    # preflight fail: missing scripts/aiosctl triggers targeted exit code.
    repo_preflight = tmp_path / "repo-preflight"
    lock_preflight = tmp_path / "locks" / "preflight.lock"
    log_preflight = tmp_path / "logs" / "preflight.log"
    _prepare_fake_repo(repo_preflight, with_aiosctl=False)
    preflight = _run_entrypoint(repo_preflight, lock_preflight, log_preflight)
    assert preflight.returncode == 42
    assert "night-preflight failed code=42" in preflight.stderr

    # lock conflict: active pid inside lock yields conflict exit code.
    repo_conflict = tmp_path / "repo-conflict"
    lock_conflict = tmp_path / "locks" / "conflict.lock"
    log_conflict = tmp_path / "logs" / "conflict.log"
    _prepare_fake_repo(repo_conflict, with_aiosctl=True)
    lock_conflict.parent.mkdir(parents=True, exist_ok=True)
    lock_conflict.write_text(f"pid={os.getpid()}\nstarted_epoch=9999999999\n", encoding="utf-8")
    conflict = _run_entrypoint(repo_conflict, lock_conflict, log_conflict)
    assert conflict.returncode == 61
    assert "run-lock conflict: active pid=" in conflict.stderr

    # stale lock: dead pid + stale timestamp should be removed and continue.
    repo_stale = tmp_path / "repo-stale"
    lock_stale = tmp_path / "locks" / "stale.lock"
    log_stale = tmp_path / "logs" / "stale.log"
    _prepare_fake_repo(repo_stale, with_aiosctl=True)
    lock_stale.parent.mkdir(parents=True, exist_ok=True)
    lock_stale.write_text("pid=999999\nstarted_epoch=1\n", encoding="utf-8")
    stale = _run_entrypoint(repo_stale, lock_stale, log_stale, stale_seconds="1")
    assert stale.returncode == 0, stale.stderr
    assert not lock_stale.exists()

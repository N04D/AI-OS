from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TextIO

from supervisor.paths import resolve_host_state_dir

try:
    import readline as _READLINE
except ImportError:  # pragma: no cover - platform dependent
    _READLINE = None


REPORTS_DIR = Path("state/night-reports")
HOST_STATE_DIR = resolve_host_state_dir()
BUDGET_LOG_PATH = HOST_STATE_DIR / "autonomy" / "budget-log.jsonl"
INTAKE_LOG_PATH = HOST_STATE_DIR / "autonomy" / "intake-log.jsonl"
TASKS_DIR = HOST_STATE_DIR / "autonomy" / "inbox" / "tasks"
DEFAULT_HISTORY_PATH = HOST_STATE_DIR / "aiosctl" / "history"
SENSITIVE_HISTORY_SUBSTRINGS = ("gitea_token", "token", "--token", "authorization", "bearer")


def _is_json_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def _stream_pipe(pipe: TextIO, output: TextIO) -> None:
    for line in iter(pipe.readline, ""):
        if _is_json_line(line):
            output.write(line)
        else:
            output.write(line)
        output.flush()


def _run_streaming(command: list[str]) -> int:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    threads = [
        threading.Thread(target=_stream_pipe, args=(process.stdout, sys.stdout), daemon=True),
        threading.Thread(target=_stream_pipe, args=(process.stderr, sys.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()

    exit_code = process.wait()
    for thread in threads:
        thread.join(timeout=2)
    return int(exit_code)


class _Watcher:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        if self.kind == "reports":
            self._watch_dir(REPORTS_DIR)
        elif self.kind == "tasks":
            self._watch_dir(TASKS_DIR)
        elif self.kind == "budget":
            self._watch_file(BUDGET_LOG_PATH)
        elif self.kind == "intake":
            self._watch_file(INTAKE_LOG_PATH)

    def _watch_dir(self, path: Path) -> None:
        seen: set[str] = set()
        while not self._stop.is_set():
            if path.is_dir():
                current = sorted(p.name for p in path.iterdir() if p.is_file())
                for item in current:
                    if item not in seen:
                        print(f"[watch:{self.kind}] {path / item}")
                seen = set(current)
            time.sleep(1)

    def _watch_file(self, path: Path) -> None:
        offset = 0
        while not self._stop.is_set():
            if path.is_file():
                with path.open("r", encoding="utf-8") as fh:
                    fh.seek(offset)
                    chunk = fh.read()
                    offset = fh.tell()
                if chunk:
                    for line in chunk.splitlines():
                        print(f"[watch:{self.kind}] {line}")
            time.sleep(1)


def _latest_report_path() -> Path | None:
    if not REPORTS_DIR.is_dir():
        return None
    files = sorted(p for p in REPORTS_DIR.iterdir() if p.is_file())
    if not files:
        return None
    return files[-1]


def _print_help() -> None:
    print("Commands:")
    print("  help")
    print("  exit")
    print("  run autonomy promote|intake|materialize|dryrun")
    print("  run night")
    print("  watch reports|budget|intake|tasks")
    print("  stop")
    print("  last report")
    print("  show report <path>")


def _history_path() -> Path:
    host_state_dir = os.environ.get("HOST_STATE_DIR", "").strip()
    if host_state_dir:
        return Path(host_state_dir) / "aiosctl" / "history"
    return DEFAULT_HISTORY_PATH


def _should_store_history(command: str) -> bool:
    lower = command.lower()
    return not any(pattern in lower for pattern in SENSITIVE_HISTORY_SUBSTRINGS)


def _load_history(readline_module: object, history_path: Path) -> None:
    set_auto_history = getattr(readline_module, "set_auto_history", None)
    if callable(set_auto_history):
        set_auto_history(False)
    if history_path.is_file():
        readline_module.read_history_file(str(history_path))


def _save_history(readline_module: object, history_path: Path) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    readline_module.write_history_file(str(history_path))


def main(argv: list[str] | None = None) -> int:
    if argv:
        print("console does not accept positional arguments")
        return 1

    watcher: _Watcher | None = None
    interactive = sys.stdin.isatty()
    readline_module: object | None = _READLINE if interactive else None
    history_path: Path | None = _history_path() if readline_module is not None else None
    if readline_module is not None and history_path is not None:
        _load_history(readline_module, history_path)

    try:
        while True:
            try:
                if interactive:
                    raw = input("aios> ")
                else:
                    raw = sys.stdin.readline()
                    if raw == "":
                        return 0
            except EOFError:
                return 0

            command = raw.strip()
            if not command:
                continue

            if readline_module is not None and _should_store_history(command):
                add_history = getattr(readline_module, "add_history", None)
                if callable(add_history):
                    add_history(command)

            parts = shlex.split(command)
            if parts == ["help"]:
                _print_help()
                continue
            if parts == ["exit"]:
                if watcher is not None:
                    watcher.stop()
                return 0
            if parts == ["stop"]:
                if watcher is not None:
                    watcher.stop()
                    watcher = None
                    print("watchers stopped")
                else:
                    print("no active watchers")
                continue
            if parts[:2] == ["watch", "reports"] and len(parts) == 2:
                if watcher is not None:
                    watcher.stop()
                watcher = _Watcher("reports")
                watcher.start()
                print("watching reports")
                continue
            if parts[:2] == ["watch", "budget"] and len(parts) == 2:
                if watcher is not None:
                    watcher.stop()
                watcher = _Watcher("budget")
                watcher.start()
                print("watching budget")
                continue
            if parts[:2] == ["watch", "intake"] and len(parts) == 2:
                if watcher is not None:
                    watcher.stop()
                watcher = _Watcher("intake")
                watcher.start()
                print("watching intake")
                continue
            if parts[:2] == ["watch", "tasks"] and len(parts) == 2:
                if watcher is not None:
                    watcher.stop()
                watcher = _Watcher("tasks")
                watcher.start()
                print("watching tasks")
                continue
            if parts == ["last", "report"]:
                report = _latest_report_path()
                if report is None:
                    print("no reports found")
                else:
                    print(str(report))
                continue
            if len(parts) == 3 and parts[0] == "show" and parts[1] == "report":
                report_path = Path(parts[2])
                if not report_path.is_file():
                    print(f"report not found: {report_path}")
                    continue
                with report_path.open("r", encoding="utf-8") as fh:
                    sys.stdout.write(fh.read())
                sys.stdout.flush()
                continue
            if parts == ["run", "night"]:
                _run_streaming(["./scripts/night-executor.sh"])
                continue
            if len(parts) == 3 and parts[:2] == ["run", "autonomy"] and parts[2] in {
                "promote",
                "intake",
                "materialize",
                "dryrun",
            }:
                _run_streaming(["./scripts/aiosctl", "autonomy", parts[2]])
                continue

            print("unknown command; run 'help'")
    finally:
        if readline_module is not None and history_path is not None:
            _save_history(readline_module, history_path)


if __name__ == "__main__":
    raise SystemExit(main())

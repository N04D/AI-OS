from __future__ import annotations

import io
import json
import os
import pty
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

from supervisor import cli
from supervisor import console


class ConsoleIntegrationTests(unittest.TestCase):
    def test_cli_console_subcommand_routes_to_console_main(self) -> None:
        with patch("supervisor.console.main", return_value=0) as mocked:
            code = cli.main(["console"])
        self.assertEqual(code, 0)
        mocked.assert_called_once_with()

    def test_console_invocation_does_not_break_cli_json(self) -> None:
        mocked = [{"status": "existing", "pr_number": 7}]
        with patch("supervisor.cli.create_draft_proposals_prs", return_value=mocked):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--json", "autonomy", "promote"])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().strip(), json.dumps({"promotion": mocked}, sort_keys=True))

    def test_scripts_aiosctl_tty_no_args_routes_to_console(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "scripts").mkdir(parents=True, exist_ok=True)
            (tmp / "bin").mkdir(parents=True, exist_ok=True)

            src = Path(__file__).resolve().parents[2] / "scripts" / "aiosctl"
            dst = tmp / "scripts" / "aiosctl"
            shutil.copy2(src, dst)
            dst.chmod(0o755)

            observed = tmp / "observed_python_argv.txt"
            fake_python = tmp / "bin" / "python"
            fake_python.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
echo "$@" > "${OBSERVED_PYTHON_ARGS:?missing OBSERVED_PYTHON_ARGS}"
exit 0
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = dict(os.environ)
            env["PATH"] = f"{tmp / 'bin'}:{env.get('PATH', '')}"
            env["OBSERVED_PYTHON_ARGS"] = str(observed)

            try:
                master_fd, slave_fd = pty.openpty()
            except OSError as exc:
                self.skipTest(f"pty unavailable in test environment: {exc}")
            try:
                proc = subprocess.run(
                    ["bash", str(dst)],
                    cwd=tmp,
                    stdin=slave_fd,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
            finally:
                os.close(master_fd)
                os.close(slave_fd)

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(observed.read_text(encoding="utf-8").strip(), "-m supervisor.console")

    def test_readline_history_load_and_write_when_tty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_file = Path(tmp_dir) / "aiosctl" / "history"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history_file.write_text("help\n", encoding="utf-8")

            mock_readline = Mock()
            with patch.dict(os.environ, {"HOST_STATE_DIR": tmp_dir}, clear=False):
                with patch("supervisor.console._READLINE", mock_readline):
                    with patch("supervisor.console.sys.stdin.isatty", return_value=True):
                        with patch("builtins.input", side_effect=["help", "exit"]):
                            code = console.main()

        self.assertEqual(code, 0)
        mock_readline.read_history_file.assert_called_once_with(str(history_file))
        mock_readline.write_history_file.assert_called_once_with(str(history_file))
        self.assertEqual(mock_readline.add_history.call_count, 2)

    def test_history_filter_blocks_sensitive_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_file = Path(tmp_dir) / "aiosctl" / "history"
            mock_readline = Mock()
            with patch.dict(os.environ, {"HOST_STATE_DIR": tmp_dir}, clear=False):
                with patch("supervisor.console._READLINE", mock_readline):
                    with patch("supervisor.console.sys.stdin.isatty", return_value=True):
                        with patch("builtins.input", side_effect=["run autonomy promote --token abc", "exit"]):
                            code = console.main()

        self.assertEqual(code, 0)
        mock_readline.write_history_file.assert_called_once_with(str(history_file))
        mock_readline.add_history.assert_called_once_with("exit")


if __name__ == "__main__":
    unittest.main()

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
from unittest.mock import patch

from supervisor import cli


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

            master_fd, slave_fd = pty.openpty()
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


if __name__ == "__main__":
    unittest.main()

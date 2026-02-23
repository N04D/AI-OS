from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


EXPECTED_QUEUE = """mode: night-autonomy-dryrun-v0.1
max_tasks: 0
max_commits: 0
max_attempts_per_task: 1
stop_on_first_failure: true
allowed_paths:
  - supervisor/
forbidden_paths:
  - executor/runtime/
task_sources: []
"""


class NightAutonomyWrapperTests(unittest.TestCase):
    def test_wrapper_creates_and_removes_temp_queue_and_keeps_repo_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "scripts").mkdir(parents=True, exist_ok=True)
            (tmp / "governance").mkdir(parents=True, exist_ok=True)
            (tmp / "governance" / "night-queue.yaml").write_text("mode: night-v0.1\n", encoding="utf-8")

            wrapper_src = Path(__file__).resolve().parents[2] / "scripts" / "night-autonomy-dryrun.sh"
            wrapper_dst = tmp / "scripts" / "night-autonomy-dryrun.sh"
            shutil.copy2(wrapper_src, wrapper_dst)
            wrapper_dst.chmod(0o755)

            fake_executor = tmp / "scripts" / "night-executor.sh"
            fake_executor.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
QUEUE_PATH="${1:?queue path required}"
echo "$QUEUE_PATH" > "${OBSERVED_QUEUE_PATH_FILE:?missing OBSERVED_QUEUE_PATH_FILE}"
cat "$QUEUE_PATH" > "${OBSERVED_QUEUE_CONTENT_FILE:?missing OBSERVED_QUEUE_CONTENT_FILE}"
exit 7
""",
                encoding="utf-8",
            )
            fake_executor.chmod(0o755)

            subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
                cwd=tmp,
                check=True,
                capture_output=True,
            )

            env = dict(os.environ)
            with tempfile.TemporaryDirectory() as external_tmp:
                ext = Path(external_tmp)
                env["TMPDIR"] = str(ext)
                observed_queue_path_file = ext / "observed_queue_path.txt"
                observed_queue_content_file = ext / "observed_queue_content.txt"
                env["OBSERVED_QUEUE_PATH_FILE"] = str(observed_queue_path_file)
                env["OBSERVED_QUEUE_CONTENT_FILE"] = str(observed_queue_content_file)
                proc = subprocess.run(
                    ["bash", "scripts/night-autonomy-dryrun.sh"],
                    cwd=tmp,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 7)

                observed_path = observed_queue_path_file.read_text(encoding="utf-8").strip()
                observed_content = observed_queue_content_file.read_text(encoding="utf-8")
                self.assertEqual(observed_content, EXPECTED_QUEUE)
                self.assertFalse(Path(observed_path).exists())

            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=tmp,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(status.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()

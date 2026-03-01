from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor.agent_workspace import AgentWorkspaceError
from supervisor.agent_workspace import push_workspace_pr
from supervisor.agent_workspace import resolve_workspace_paths
from supervisor.agent_workspace import sync_workspace


def _git(repo: Path, args: list[str]) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


class AgentWorkspaceTests(unittest.TestCase):
    def test_resolve_workspace_paths_uses_deterministic_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = resolve_workspace_paths("agent-1", workspace_root=tmp_dir)
            self.assertEqual(paths.root, Path(tmp_dir))
            self.assertEqual(paths.agent_root, Path(tmp_dir) / "agent-1")
            self.assertEqual(paths.repo, Path(tmp_dir) / "agent-1" / "repo")
            self.assertEqual(paths.env, Path(tmp_dir) / "agent-1" / "env")
            self.assertEqual(paths.logs, Path(tmp_dir) / "agent-1" / "logs")
            self.assertEqual(paths.runtime_env_file, Path(tmp_dir) / "agent-1" / "env" / ".env.runtime")
            self.assertEqual(paths.mailbox_fixtures_dir, Path(tmp_dir) / "agent-1" / "env" / "mailboxes")

    def test_sync_workspace_creates_env_and_logs_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bare = tmp / "origin.git"
            source = tmp / "source"
            _git(tmp, ["init", "--bare", str(bare)])

            source.mkdir(parents=True, exist_ok=True)
            _git(source, ["init"])
            _git(source, ["checkout", "-b", "dev"])
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            _git(source, ["add", "README.md"])
            _git(source, ["-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "init"])
            _git(source, ["remote", "add", "origin", str(bare)])
            _git(source, ["push", "-u", "origin", "dev"])

            workspace_root = tmp / "workspaces"
            result = sync_workspace(
                repo_root=source,
                agent="alpha",
                workspace_root=str(workspace_root),
                base_branch="dev",
            )
            self.assertEqual(result["status"], "ok")
            ws = workspace_root / "alpha"
            self.assertTrue((ws / "repo" / ".git").is_dir())
            self.assertTrue((ws / "env").is_dir())
            self.assertTrue((ws / "logs").is_dir())
            self.assertTrue((ws / "env" / "mailboxes").is_dir())
            self.assertEqual((ws / ".gitignore").read_text(encoding="utf-8"), "env/\nlogs/\n")

    def test_sync_workspace_accepts_remote_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bare = tmp / "origin.git"
            source = tmp / "source"
            _git(tmp, ["init", "--bare", str(bare)])

            source.mkdir(parents=True, exist_ok=True)
            _git(source, ["init"])
            _git(source, ["checkout", "-b", "dev"])
            (source / "README.md").write_text("hello\n", encoding="utf-8")
            _git(source, ["add", "README.md"])
            _git(source, ["-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "init"])
            _git(source, ["remote", "add", "origin", str(bare)])
            _git(source, ["push", "-u", "origin", "dev"])

            workspace_root = tmp / "workspaces"
            result = sync_workspace(
                repo_root=source,
                agent="beta",
                workspace_root=str(workspace_root),
                base_branch="dev",
                remote=str(bare),
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["remote"], str(bare))

    def test_push_pr_is_mockable_and_clean_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir) / "agents" / "delta" / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / ".git").mkdir()

            def fake_run_git(repo_root: Path, args: list[str]) -> str:
                if args == ["status", "--porcelain"]:
                    return ""
                if args == ["branch", "--show-current"]:
                    return "feature-x"
                if args[:3] == ["push", "-u", "origin"]:
                    return ""
                if args == ["remote", "get-url", "origin"]:
                    return "git@localhost:N04D/AI-OS.git"
                raise AssertionError(f"unexpected git call: {args}")

            with (
                patch("supervisor.agent_workspace._run_git", side_effect=fake_run_git),
                patch("supervisor.agent_workspace._api_json_request", return_value=(201, {"number": 42, "html_url": "http://g/pr/42"})),
                patch.dict("os.environ", {"GITEA_TOKEN": "token", "GITEA_BASE_URL": "http://127.0.0.1:3000"}, clear=False),
            ):
                result = push_workspace_pr(
                    agent="delta",
                    title="t",
                    body="b",
                    base_branch="dev",
                    workspace_root=str(Path(tmp_dir) / "agents"),
                )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["pr_number"], 42)
            self.assertEqual(result["branch"], "feature-x")

    def test_push_pr_rejects_dirty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir) / "agents" / "delta" / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / ".git").mkdir()

            def fake_run_git(repo_root: Path, args: list[str]) -> str:
                if args == ["status", "--porcelain"]:
                    return " M file.txt"
                raise AssertionError(f"unexpected git call: {args}")

            with patch("supervisor.agent_workspace._run_git", side_effect=fake_run_git):
                with self.assertRaises(AgentWorkspaceError) as ctx:
                    push_workspace_pr(
                        agent="delta",
                        title="t",
                        body="b",
                        workspace_root=str(Path(tmp_dir) / "agents"),
                    )
            self.assertEqual(ctx.exception.reason_code, "DENY_DIRTY_WORKTREE")


if __name__ == "__main__":
    unittest.main()

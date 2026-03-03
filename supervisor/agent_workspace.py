from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aios.secrets.context import ContextFactory
from aios.secrets.integration import resolve_gitea_token
from supervisor.gitea_config import resolve_gitea_base_url

DEFAULT_WORKSPACE_ROOT = Path("/var/lib/aios/agents")


class AgentWorkspaceError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    agent_root: Path
    repo: Path
    env: Path
    logs: Path
    venv: Path
    runtime_env_file: Path
    mailbox_fixtures_dir: Path


def _normalize_name(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_INVALID", f"{field} is required")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
        raise AgentWorkspaceError(
            "DENY_AGENT_WORKSPACE_INVALID",
            f"{field} contains unsupported characters",
        )
    return normalized


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_GIT_FAILED", (proc.stderr or proc.stdout or "git failed").strip())
    return proc.stdout.strip()


def _workspace_root(base: str | None = None) -> Path:
    if base is not None and base.strip():
        return Path(base.strip()).expanduser()
    env_root = os.environ.get("AIOS_AGENT_WORKSPACE_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser()
    return DEFAULT_WORKSPACE_ROOT


def resolve_workspace_paths(agent: str, *, workspace_root: str | None = None) -> WorkspacePaths:
    agent_name = _normalize_name(agent, field="agent")
    root = _workspace_root(workspace_root)
    agent_root = root / agent_name
    env_dir = agent_root / "env"
    return WorkspacePaths(
        root=root,
        agent_root=agent_root,
        repo=agent_root / "repo",
        env=env_dir,
        logs=agent_root / "logs",
        venv=agent_root / "venv",
        runtime_env_file=env_dir / ".env.runtime",
        mailbox_fixtures_dir=env_dir / "mailboxes",
    )


def _ensure_workspace_layout(paths: WorkspacePaths) -> None:
    paths.repo.parent.mkdir(parents=True, exist_ok=True)
    paths.env.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)
    paths.mailbox_fixtures_dir.mkdir(parents=True, exist_ok=True)
    workspace_gitignore = paths.agent_root / ".gitignore"
    workspace_gitignore.write_text("env/\nlogs/\nvenv/\n", encoding="utf-8")


def _resolve_source_remote(repo_root: Path) -> str:
    for remote in ("gitea", "origin"):
        proc = subprocess.run(
            ["git", "remote", "get-url", remote],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            value = proc.stdout.strip()
            if value:
                return value
    raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_REMOTE_MISSING", "missing source remote url")


def _remote_owner_repo(remote_url: str) -> tuple[str, str]:
    value = remote_url.strip()
    patterns = [
        r"ssh://git@[^/]+/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"git@[^:]+:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"https?://[^/]+/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            return match.group("owner"), match.group("repo")
    raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_REMOTE_INVALID", f"unsupported remote url: {value}")


def _normalize_api_base(base_url: str) -> str:
    base = base_url.rstrip("/")
    if not base:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_ENV_MISSING", "GITEA_BASE_URL is required")
    if base.endswith("/api/v1"):
        return base
    if "/api/v1" in base:
        return base.split("/api/v1", 1)[0] + "/api/v1"
    return f"{base}/api/v1"


def _api_json_request(method: str, url: str, token: str, payload: dict[str, Any]) -> tuple[int, Any]:
    headers = {"Accept": "application/json", "Authorization": f"token {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            parsed: Any = json.loads(body) if body else None
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        parsed = {"raw": raw}
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw}
        return exc.code, parsed


def sync_workspace(
    *,
    repo_root: Path,
    agent: str,
    workspace_root: str | None = None,
    base_branch: str = "dev",
    remote: str = "",
) -> dict[str, Any]:
    branch = _normalize_name(base_branch, field="base_branch")
    paths = resolve_workspace_paths(agent, workspace_root=workspace_root)
    _ensure_workspace_layout(paths)
    remote_url = remote.strip() or _resolve_source_remote(repo_root)
    if not (paths.repo / ".git").is_dir():
        proc = subprocess.run(
            ["git", "clone", remote_url, str(paths.repo)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_GIT_FAILED", (proc.stderr or proc.stdout or "git clone failed").strip())
    else:
        _run_git(paths.repo, ["remote", "set-url", "origin", remote_url])

    _run_git(paths.repo, ["fetch", "--prune", "origin"])
    _run_git(paths.repo, ["checkout", "-B", branch, f"origin/{branch}"])
    _run_git(paths.repo, ["reset", "--hard", f"origin/{branch}"])
    _run_git(paths.repo, ["clean", "-fd"])
    return {
        "status": "ok",
        "agent": _normalize_name(agent, field="agent"),
        "workspace_repo": str(paths.repo),
        "runtime_env_file": str(paths.runtime_env_file),
        "mailbox_fixtures_dir": str(paths.mailbox_fixtures_dir),
        "base_branch": branch,
        "remote": remote_url,
    }


def run_workspace_tests(*, agent: str, workspace_root: str | None = None) -> dict[str, Any]:
    paths = resolve_workspace_paths(agent, workspace_root=workspace_root)
    if not (paths.repo / ".git").is_dir():
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_MISSING", "workspace repo missing; run sync first")
    env = dict(os.environ)
    env["AIOS_ENV_FILE"] = str(paths.runtime_env_file)
    env["AIOS_MAILBOX_FIXTURES_DIR"] = str(paths.mailbox_fixtures_dir)
    python3_bin = os.environ.get("AIOS_PYTHON3_BIN", "").strip() or "python3"
    ensure_commands: list[list[str]] = []
    if not (paths.venv / "bin" / "python").is_file():
        create_venv = subprocess.run(
            [python3_bin, "-m", "venv", str(paths.venv)],
            cwd=paths.repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if create_venv.returncode != 0:
            raise AgentWorkspaceError(
                "DENY_AGENT_WORKSPACE_RUNTIME_MISSING",
                (create_venv.stderr or create_venv.stdout or "python3 venv creation failed").strip(),
            )
        ensure_commands.append([python3_bin, "-m", "venv", str(paths.venv)])

    venv_python = paths.venv / "bin" / "python"
    pip_check_command = [str(venv_python), "-m", "pip", "--version"]
    pip_check_proc = subprocess.run(
        pip_check_command,
        cwd=paths.repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if pip_check_proc.returncode != 0:
        ensurepip_command = [str(venv_python), "-m", "ensurepip", "--upgrade"]
        ensurepip_proc = subprocess.run(
            ensurepip_command,
            cwd=paths.repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if ensurepip_proc.returncode != 0:
            return {
                "status": "failed",
                "agent": _normalize_name(agent, field="agent"),
                "workspace_repo": str(paths.repo),
                "runtime_env_file": str(paths.runtime_env_file),
                "mailbox_fixtures_dir": str(paths.mailbox_fixtures_dir),
                "venv_path": str(paths.venv),
                "command": " ".join(ensurepip_command),
                "exit_code": int(ensurepip_proc.returncode),
                "stdout_tail": "\n".join(ensurepip_proc.stdout.splitlines()[-10:]),
                "stderr_tail": "\n".join(ensurepip_proc.stderr.splitlines()[-10:]),
                "bootstrap_commands": [" ".join(cmd) for cmd in ensure_commands],
            }
        ensure_commands.append(ensurepip_command)

    requirements = paths.repo / "requirements.txt"
    requirements_dev = paths.repo / "requirements-dev.txt"
    install_commands: list[list[str]] = []
    if requirements.is_file():
        install_commands.append([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"])
    if requirements_dev.is_file():
        install_commands.append([str(venv_python), "-m", "pip", "install", "-r", "requirements-dev.txt"])
    if not install_commands:
        install_commands.append([str(venv_python), "-m", "pip", "install", "pytest"])

    for install_command in install_commands:
        install_proc = subprocess.run(
            install_command,
            cwd=paths.repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if install_proc.returncode != 0:
            return {
                "status": "failed",
                "agent": _normalize_name(agent, field="agent"),
                "workspace_repo": str(paths.repo),
                "runtime_env_file": str(paths.runtime_env_file),
                "mailbox_fixtures_dir": str(paths.mailbox_fixtures_dir),
                "venv_path": str(paths.venv),
                "command": " ".join(install_command),
                "exit_code": int(install_proc.returncode),
                "stdout_tail": "\n".join(install_proc.stdout.splitlines()[-10:]),
                "stderr_tail": "\n".join(install_proc.stderr.splitlines()[-10:]),
                "bootstrap_commands": [" ".join(cmd) for cmd in ensure_commands],
            }

    test_command = [str(venv_python), "-m", "pytest", "-q"]
    proc = subprocess.run(
        test_command,
        cwd=paths.repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "agent": _normalize_name(agent, field="agent"),
        "workspace_repo": str(paths.repo),
        "runtime_env_file": str(paths.runtime_env_file),
        "mailbox_fixtures_dir": str(paths.mailbox_fixtures_dir),
        "venv_path": str(paths.venv),
        "command": " ".join(test_command),
        "exit_code": int(proc.returncode),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-10:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-10:]),
        "bootstrap_commands": [" ".join(cmd) for cmd in ensure_commands + install_commands],
    }


def create_workspace_branch(*, agent: str, branch_name: str, workspace_root: str | None = None) -> dict[str, Any]:
    paths = resolve_workspace_paths(agent, workspace_root=workspace_root)
    branch = _normalize_name(branch_name, field="branch")
    if not (paths.repo / ".git").is_dir():
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_MISSING", "workspace repo missing; run sync first")
    dirty = _run_git(paths.repo, ["status", "--porcelain"]).strip()
    if dirty:
        raise AgentWorkspaceError("DENY_DIRTY_WORKTREE", "workspace repo must be clean before branch creation")
    _run_git(paths.repo, ["checkout", "-B", branch])
    return {"status": "ok", "agent": _normalize_name(agent, field="agent"), "workspace_repo": str(paths.repo), "branch": branch}


def push_workspace_pr(
    *,
    agent: str,
    title: str,
    body: str,
    base_branch: str = "dev",
    workspace_root: str | None = None,
) -> dict[str, Any]:
    paths = resolve_workspace_paths(agent, workspace_root=workspace_root)
    if not (paths.repo / ".git").is_dir():
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_MISSING", "workspace repo missing; run sync first")
    if _run_git(paths.repo, ["status", "--porcelain"]).strip():
        raise AgentWorkspaceError("DENY_DIRTY_WORKTREE", "workspace repo must be clean before push-pr")
    token = resolve_gitea_token(
        context=ContextFactory.supervisor_agent_workspace_push_pr(),
    )
    if not token:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_SECRET_MISSING", "Secret key 'gitea.token' is required")
    api_base = _normalize_api_base(resolve_gitea_base_url())
    current_branch = _run_git(paths.repo, ["branch", "--show-current"]).strip()
    if not current_branch:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_GIT_FAILED", "could not resolve current branch")

    _run_git(paths.repo, ["push", "-u", "origin", current_branch])
    remote_url = _run_git(paths.repo, ["remote", "get-url", "origin"]).strip()
    owner, repo = _remote_owner_repo(remote_url)

    payload = {
        "title": title.strip(),
        "body": body.strip(),
        "head": current_branch,
        "base": _normalize_name(base_branch, field="base_branch"),
        "draft": True,
    }
    if not payload["title"]:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_INVALID", "title is required")
    if not payload["body"]:
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_INVALID", "body is required")

    status, response = _api_json_request(
        "POST",
        f"{api_base}/repos/{owner}/{repo}/pulls",
        token,
        payload,
    )
    if status not in (200, 201) or not isinstance(response, dict):
        raise AgentWorkspaceError("DENY_AGENT_WORKSPACE_PR_FAILED", f"pull_create_failed:{status}")
    return {
        "status": "ok",
        "agent": _normalize_name(agent, field="agent"),
        "workspace_repo": str(paths.repo),
        "branch": current_branch,
        "pr_number": response.get("number"),
        "pr_url": response.get("html_url"),
    }

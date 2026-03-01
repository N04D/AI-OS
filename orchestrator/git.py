import json
import re
import subprocess
import urllib.request
from datetime import UTC
from datetime import datetime
from pathlib import Path

from supervisor.control_plane import BudgetStateError
from supervisor.control_plane import consume_from_path
from supervisor.git_remote import preferred_remote_name


def run(cmd):
    subprocess.run(cmd, check=True)


def get_diff():
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def create_branch(task_id):
    branch = f"feature/task-{task_id}"
    run(["git", "checkout", "-b", branch])
    return branch


def commit(message, files=None):
    staged_files = list(files) if files is not None else get_changed_files()
    if not staged_files:
        return
    run(["git", "add", "--", *staged_files])
    run(["git", "commit", "-m", message])


def push(branch):
    run(["git", "push", "-u", preferred_remote_name(), branch])


def get_repo_info():
    remote_name = preferred_remote_name()
    result = subprocess.run(
        ["git", "config", "--get", f"remote.{remote_name}.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    url = result.stdout.strip()

    match_ssh_full = re.search(r"ssh://git@(?P<host>[^:]+):(?P<port>\d+)/(?P<owner>[^/]+)/(?P<repo>.+)\.git", url)
    if match_ssh_full:
        info = match_ssh_full.groupdict()
        return info["host"], info["port"], info["owner"], info["repo"]

    match_ssh = re.search(r"(?:(?P<user>[^@]+)@)?(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>.+)\.git", url)
    if match_ssh:
        info = match_ssh.groupdict()
        return info["host"], "3000", info["owner"], info["repo"]

    match_http = re.search(r"https?://(?P<host>[^:]+)(:(?P<port>\d+))?/(?P<owner>[^/]+)/(?P<repo>.+)\.git", url)
    if match_http:
        info = match_http.groupdict()
        port = info.get("port") or ("443" if url.startswith("https") else "80")
        return info["host"], port, info["owner"], info["repo"]

    raise ValueError(f"Unsupported or non-Gitea git remote URL format (remote={remote_name}): {url}")


def get_open_issues():
    host, port, owner, repo = get_repo_info()
    candidate_hosts = [host]
    if host == "gitea":
        # Common local install where git remote uses "gitea" alias but HTTP is on localhost.
        candidate_hosts.append("localhost")

    last_error = None
    for candidate_host in candidate_hosts:
        api_url = f"http://{candidate_host}:{port}/api/v1/repos/{owner}/{repo}/issues"
        try:
            with urllib.request.urlopen(api_url) as response:
                data = json.loads(response.read().decode())
                return [{"number": i["number"], "title": i["title"]} for i in data]
        except urllib.error.URLError as e:
            last_error = (e, api_url)

    if last_error is not None:
        err, url = last_error
        print(f"Error fetching issues from Gitea API: {err}")
        print(f"Attempted to connect to: {url}")
    return []


def create_governed_commit(result, dispatch_input, *, now_utc=None, budget_state_path=None):
    changed_files = sorted(set(result.changed_files or []))
    allowed_files = set(dispatch_input.get("allowed_files", []))
    task_id = dispatch_input.get("task_id")

    if not changed_files:
        return {
            "commit_created": False,
            "commit_hash": None,
            "files_committed": [],
        }

    if not set(changed_files).issubset(allowed_files):
        return {
            "commit_created": False,
            "commit_hash": None,
            "files_committed": [],
        }

    commit_message = str(dispatch_input.get("commit_message") or f"feat(task-{task_id}): governed executor result")

    try:
        safe_now = now_utc if isinstance(now_utc, datetime) else datetime.now(UTC)
        try:
            budget_result = consume_from_path(
                Path(str(budget_state_path)) if budget_state_path else Path("state/budgets.json"),
                "low_risk_pr_merge",
                safe_now,
                cost=1,
            )
        except BudgetStateError as exc:
            return {
                "commit_created": False,
                "commit_hash": None,
                "files_committed": [],
                "reason_code": exc.reason_code,
                "budget_key": "low_risk_pr_merge",
            }

        if not budget_result.get("ok", False):
            snapshot = budget_result.get("snapshot") if isinstance(budget_result.get("snapshot"), dict) else {}
            return {
                "commit_created": False,
                "commit_hash": None,
                "files_committed": [],
                "reason_code": budget_result.get("reason_code", "DENY_BUDGET_EXCEEDED"),
                "budget_key": snapshot.get("budget_key", "low_risk_pr_merge"),
                "limit": snapshot.get("limit"),
                "used": snapshot.get("used"),
                "window_start_utc": snapshot.get("window_start_utc"),
            }

        subprocess.run(["git", "add", "--", *changed_files], check=True)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--", *changed_files],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        staged = [x.strip() for x in staged if x.strip()]

        commit_cmd = ["git", "commit", "--allow-empty", "-m", commit_message, "--", *changed_files]
        subprocess.run(
            commit_cmd,
            check=True,
        )
        commit_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {
            "commit_created": True,
            "commit_hash": commit_hash,
            "files_committed": staged if staged else changed_files,
        }
    except subprocess.CalledProcessError:
        return {
            "commit_created": False,
            "commit_hash": None,
            "files_committed": [],
        }

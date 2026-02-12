import subprocess
import json
import urllib.request

def run(cmd):
    subprocess.run(cmd, check=True)

def get_diff():
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True,
        text=True
    )
    return result.stdout

def create_branch(task_id):
    branch = f"feature/task-{task_id}"
    run(["git", "checkout", "-b", branch])
    return branch

def commit(message):
    run(["git", "add", "."])
    run(["git", "commit", "-m", message])

def push(branch):
    run(["git", "push", "-u", "origin", branch])

def get_repo_owner_and_name():
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True
    )
    url = result.stdout.strip()
    # git@github.com:owner/repo.git
    owner, repo = url.split(":")[-1].split("/")
    repo = repo.replace(".git", "")
    return owner, repo

def get_open_issues():
    owner, repo = get_repo_owner_and_name()
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        return [{"number": i["number"], "title": i["title"]} for i in data]

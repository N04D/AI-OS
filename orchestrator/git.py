import subprocess
import json
import urllib.request
import re

def run(cmd):
    subprocess.run(cmd, check=True)

def get_diff():
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        capture_output=True,
        text=True
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

def commit(message):
    run(["git", "add", "."])
    run(["git", "commit", "-m", message])

def push(branch):
    run(["git", "push", "-u", "origin", branch])

def get_repo_info():
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True
    )
    url = result.stdout.strip()
    
    # Handle ssh://git@localhost:2222/Don/dev.git
    match = re.search(r'ssh://git@(?P<host>[^:]+):(?P<port>\d+)/(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match:
        info = match.groupdict()
        return info['host'], info['port'], info['owner'], info['repo']
    
    # Handle git@github.com:owner/repo.git
    match = re.search(r'git@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match:
        info = match.groupdict()
        info['port'] = '80' # Default port for http
        return info['host'], info['port'], info['owner'], info['repo']
        
    raise ValueError(f"Unsupported git remote URL format: {url}")


def get_open_issues():
    host, port, owner, repo = get_repo_info()

    # Assuming Gitea API is hosted on http
    api_url = f"http://{host}:{port}/api/v1/repos/{owner}/{repo}/issues"
    
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read().decode())
            return [{"number": i["number"], "title": i["title"]} for i in data]
    except urllib.error.URLError as e:
        print(f"Error fetching issues from Gitea API: {e}")
        print(f"Attempted to connect to: {api_url}")
        return []

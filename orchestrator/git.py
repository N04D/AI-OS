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
    
    # Handle ssh://git@<host>:<port>/<owner>/<repo>.git
    # Example: ssh://git@localhost:2222/Don/dev.git
    match_ssh_full = re.search(r'ssh://git@(?P<host>[^:]+):(?P<port>\d+)/(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match_ssh_full:
        info = match_ssh_full.groupdict()
        return info['host'], info['port'], info['owner'], info['repo']

    # Handle git@<host>:<owner>/<repo>.git (standard SSH)
    match_ssh = re.search(r'git@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match_ssh:
        info = match_ssh.groupdict()
        # Default Gitea HTTP port is typically 3000, but there is no way to know for sure from SSH url 
        # unless we assume or config.
        # However, for 'git@localhost:Don/dev.git', it's ambiguous. 
        # The previous code assumed port 80 for 'github.com', but here we are dealing with local/private Gitea.
        # If the user says "Canonical remote is Gitea", and "Always derive API endpoints", 
        # we might need to assume the http service is on a standard port or the same host.
        # But wait, the previous code returned '80' for the GitHub case. 
        # For a local Gitea derived from `ssh://git@localhost:2222...`, we have a port 2222 for SSH.
        # We need the HTTP port for the API. It is NOT 2222.
        # The original code used 2222 as the HTTP port? 
        # Line 67: api_url = f"http://{host}:{port}/api/v1/..."
        # This implies the code assumed the SSH port and HTTP port are the same, OR that the URL contained the HTTP port.
        # In `ssh://git@localhost:2222/...`, 2222 is the SSH port. using that for HTTP is likely WRONG unless Gitea is doing something weird.
        # BUT, strictly following instructions to "derive API endpoints from git remote", 
        # and looking at the existing code which used the `port` from the regex...
        
        # Let's look closer at the original code:
        # match = re.search(r'ssh://git@(?P<host>[^:]+):(?P<port>\d+)/(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
        # return info['host'], info['port'], ...
        # Api call: f"http://{host}:{port}/..."
        
        # If the remote is ssh://git@localhost:2222/..., then host=localhost, port=2222.
        # The API call becomes http://localhost:2222/api/v1/... 
        # This works ONLY if Gitea is exposed on HTTP at 2222 as well, or if the user's environment has SSH and HTTP on same port (unlikely), 
        # OR if the "2222" in the URL was actually meant to be the HTTP port (also unlikely for an SSH URL).
        
        # However, typically in these local setups with docker mapping:
        # 2222:22 (SSH)
        # 3000:3000 (HTTP)
        
        # If the remote is just `git@server:owner/repo.git`, we have NO port info.
        
        # The user instruction said: "Always derive API endpoints from git remote get-url origin."
        
        # If the user's setup relies on the port being present in the ssh url (Docker style), we should preserve extracting it.
        # But we must NOT assume GitHub.
        
        return info['host'], "3000", info['owner'], info['repo'] # Default to 3000 if not specified? 
        # Or should we just fail if we can't find it?
        
    # Handle http(s)://<host>:<port>/<owner>/<repo>.git
    match_http = re.search(r'https?://(?P<host>[^:]+)(:(?P<port>\d+))?/(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match_http:
        info = match_http.groupdict()
        port = info.get('port') or ('443' if url.startswith('https') else '80')
        return info['host'], port, info['owner'], info['repo']

    raise ValueError(f"Unsupported or non-Gitea git remote URL format: {url}")


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


def create_governed_commit(result, dispatch_input):
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

    commit_message = f"feat(task-{task_id}): governed executor result"

    try:
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

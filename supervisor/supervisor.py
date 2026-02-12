import json
import time
import urllib.request
import re # Added for regex operations

def get_repo_identity_from_template(git_remote_template):
    """
    Derives owner and repo from the git_remote_template.
    Expected format: ssh://git@localhost:2222/{owner}/{repo}.git
    """
    match = re.search(r'{owner}/(?P<repo>.+)\.git', git_remote_template)
    if match:
        # Assuming owner is always "Don" for now based on the template structure,
        # but the template implies it could be dynamic if {owner} is replaced.
        # For this context, we will extract "Don" from the provided example
        # and parse the repo name.
        owner_match = re.search(r'/(?P<owner>[^/]+)/{repo}', git_remote_template)
        owner = owner_match.group('owner') if owner_match else "unknown_owner" # Fallback
        
        return owner, match.group('repo')
    else:
        raise ValueError(f"Could not parse owner and repo from git_remote_template: {git_remote_template}")

def get_open_issues(api_base, owner, repo):
    """Fetches open issues from the Gitea API."""
    api_url = f"{api_base}/repos/{owner}/{repo}/issues"
    try:
        with urllib.request.urlopen(api_url, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data
    except Exception as e:
        print(f"Error fetching issues: {e}")
    return []

def select_task(issues):
    """Deterministically selects the issue with the lowest number."""
    if not issues:
        return None
    return min(issues, key=lambda i: i['number'])

def main():
    """Main supervisor loop."""
    env_file = "agents/state/environment.json"
    
    while True:
        with open(env_file, "r") as f:
            env = json.load(f)
            
        api_base = env.get("api_base")
        git_remote_template = env.get("git_remote_template")

        if not api_base or not git_remote_template:
            print("Error: Missing api_base or git_remote_template in environment.json. Sleeping.")
            time.sleep(60)
            continue
            
        try:
            owner, repo = get_repo_identity_from_template(git_remote_template)
        except ValueError as e:
            print(f"Error: {e}. Sleeping.")
            time.sleep(60)
            continue

        issues = get_open_issues(api_base, owner, repo)
        
        if issues:
            task = select_task(issues)
            print(f"Current task: #{task['number']} - {task['title']}")
        else:
            print("No open issues found. Sleeping for 60 seconds.")
            time.sleep(60)

if __name__ == "__main__":
    main()

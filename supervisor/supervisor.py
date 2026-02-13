import json
import time
import urllib.request
import re
import subprocess # Added for git command
import sys # Added for sys.exit
try:
    from governance_enforcement import GovernanceEnforcer, GovernanceViolation
except ImportError:
    from supervisor.governance_enforcement import GovernanceEnforcer, GovernanceViolation

def get_repo_identity_from_remote_url():
    """
    Derives owner and repo from the actual git remote URL.
    Expected format: ssh://git@localhost:2222/Don/dev.git or git@github.com:owner/repo.git
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True
        )
        url = result.stdout.strip()
    except subprocess.CalledProcessError:
        raise ValueError("Could not get git remote.origin.url. Is this a git repository?")

    # Handle ssh://git@localhost:2222/Don/dev.git
    match = re.search(r'ssh://git@(?:[^:]+)(?::\d+)?/(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match:
        return match.group('owner'), match.group('repo')
    
    # Handle git@github.com:owner/repo.git
    match = re.search(r'git@(?:[^:]+):(?P<owner>[^/]+)/(?P<repo>.+)\.git', url)
    if match:
        return match.group('owner'), match.group('repo')
        
    raise ValueError(f"Unsupported git remote URL format: {url}")

def get_open_issues(api_base, owner, repo):
    """Fetches open issues from the Gitea API."""
    api_url = f"{api_base}/repos/{owner}/{repo}/issues"
    try:
        with urllib.request.urlopen(api_url, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data
    except Exception as e:
        # print(f"Error fetching issues from {api_url}: {e}") # Removed for cleaner output
        pass # The main loop will handle the 'no issues found'
    return []

def add_label_to_issue(api_base, owner, repo, issue_number, label):
    """Adds a label to a Gitea issue."""
    url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/labels"
    headers = {"Content-Type": "application/json"}
    data = json.dumps([label]).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status in [200, 201]:
                print(f"Successfully added label '{label}' to issue #{issue_number}")
                return True
            else:
                print(f"Failed to add label '{label}' to issue #{issue_number}. Status: {response.status}")
                return False
    except Exception as e:
        print(f"Error adding label '{label}' to issue #{issue_number}: {e}")
        return False

def select_task(issues):
    """Deterministically selects the issue with the lowest number."""
    if not issues:
        return None
    
    # Filter out issues that are already "in-progress"
    available_issues = [issue for issue in issues if "in-progress" not in [lbl['name'] for lbl in issue.get('labels', [])]]
    if not available_issues:
        return None

    return min(available_issues, key=lambda i: i['number'])

def main():
    """Main supervisor loop."""
    env_file = "agents/state/environment.json"
    enforcer = GovernanceEnforcer(
        governance_path="docs/governance.md",
        environment_path=env_file,
    )
    try:
        context_info = enforcer.load_context()
        print(
            "Governance context loaded "
            f"(hash={context_info['governance_hash'][:12]}...)."
        )
    except GovernanceViolation:
        print(enforcer.compliance_report_block())
        sys.exit(1)
    
    while True:
        with open(env_file, "r") as f:
            env = json.load(f)
            
        api_base = env.get("api_base")

        if not api_base:
            print("Error: Missing api_base in environment.json. Sleeping.")
            time.sleep(60)
            continue
            
        try:
            owner, repo = get_repo_identity_from_remote_url()
        except ValueError as e:
            print(f"Error: {e}. Sleeping.")
            time.sleep(60)
            continue

        issues = get_open_issues(api_base, owner, repo)
        
        if issues:
            task = select_task(issues)
            if task:
                instruction_text = task.get("title", "")
                if task.get("body"):
                    instruction_text = f"{instruction_text}\n\n{task['body']}"

                try:
                    enforcer.validate_pre_computation(
                        instruction_text=instruction_text,
                        intended_outcome=f"Claim issue #{task['number']} as in-progress",
                    )
                except GovernanceViolation:
                    print(
                        f"Rejected task #{task['number']} due to governance enforcement."
                    )
                    print(enforcer.compliance_report_block())
                    time.sleep(60)
                    continue

                print(f"Selected task: #{task['number']} - {task['title']}")
                # Attempt to claim the issue
                if add_label_to_issue(api_base, owner, repo, task['number'], "in-progress"):
                    print(f"CLAIMED issue #{task['number']}")
                    print(enforcer.compliance_report_block())
                    sys.exit(0) # Stop execution after successful claim
                else:
                    print(f"Failed to claim issue #{task['number']}. Retrying in next loop.")
            else:
                print("All open issues are already in-progress. Sleeping for 60 seconds.")
        else:
            print("No open issues found. Sleeping for 60 seconds.")
        print(enforcer.compliance_report_block())
        time.sleep(60) # Sleep even if claiming failed or all issues are in-progress

if __name__ == "__main__":
    main()

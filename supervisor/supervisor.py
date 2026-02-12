import json
import time
import urllib.request

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
        
        # A simple way to get owner/repo from the template for this context
        owner, repo = "Don", "dev"

        issues = get_open_issues(api_base, owner, repo)
        
        if issues:
            task = select_task(issues)
            print(f"Current task: #{task['number']} - {task['title']}")
        else:
            print("No open issues found. Sleeping for 60 seconds.")
            time.sleep(60)

if __name__ == "__main__":
    main()

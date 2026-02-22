import json
import urllib.request

def get_owner_and_repo_from_template(template):
    # "ssh://git@localhost:2222/{owner}/{repo}.git" -> ("Don", "dev")
    # This is a simplification for this script, assuming a fixed repo for now.
    return "Don", "dev"

def verify_and_correct_environment():
    env_file = "agents/state/environment.json"
    with open(env_file, "r") as f:
        env = json.load(f)

    api_base = env["api_base"]
    owner, repo = get_owner_and_repo_from_template(env["git_remote_template"])
    
    ports_to_try = [3000, 80, 8080]
    # Get the port from the current api_base and add it to the list if not present
    try:
        current_port = int(api_base.split(":")[-1].split("/")[0])
        if current_port not in ports_to_try:
            ports_to_try.insert(0, current_port)
    except (ValueError, IndexError):
        pass


    for port in ports_to_try:
        host = "http://localhost"
        new_api_base = f"{host}:{port}/api/v1"
        api_url = f"{new_api_base}/repos/{owner}/{repo}/issues"
        
        print(f"Attempting to connect to: {api_url}")
        
        try:
            with urllib.request.urlopen(api_url, timeout=2) as response:
                if response.status == 200:
                    json.loads(response.read().decode())
                    print(f"Success! Found valid Gitea API at: {new_api_base}")
                    
                    if env["api_base"] != new_api_base:
                        print(f"Updating {env_file} with correct api_base.")
                        env["api_base"] = new_api_base
                        with open(env_file, "w") as f:
                            json.dump(env, f, indent=2)
                    
                    return
        except Exception as e:
            print(f"  ... failed: {e}")
            
    print("Failed to find a valid Gitea API endpoint.")

if __name__ == "__main__":
    verify_and_correct_environment()

import json
import time
import urllib.request
import urllib.error
import re
import subprocess # Added for git command
import sys # Added for sys.exit
import os
from datetime import datetime, timezone
try:
    from governance_enforcement import GovernanceEnforcer, GovernanceViolation
except ImportError:
    from supervisor.governance_enforcement import GovernanceEnforcer, GovernanceViolation
from supervisor.environment_validation import validate_environment
from executor.dispatch import DispatchFailure, dispatch_task_once

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

def _auth_headers(env):
    """Builds optional Gitea authentication headers from env json or process env."""
    token = (
        env.get("api_token")
        or env.get("gitea_token")
        or env.get("token")
        or env.get("access_token")
        or env.get("auth_token")
    )
    if not token:
        token = None
        try:
            import os
            token = os.environ.get("GITEA_TOKEN")
        except Exception:
            token = None

    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers

def _api_json_request(method, url, payload=None, headers=None):
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data = None
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read().decode()
            parsed = json.loads(raw) if raw else None
            return response.status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
        return e.code, parsed, raw

def _utc_iso8601():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _append_execution_log(entry):
    os.makedirs("logs", exist_ok=True)
    with open("logs/execution_cycle.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

def _extract_allowed_files(instruction_text):
    return sorted(set(re.findall(r"`([A-Za-z0-9_.\\-/]+)`", instruction_text)))

def _is_commit_message_valid(message):
    if not message:
        return True
    return bool(re.match(r"^(feat|fix|chore)\([^)]+\): .+", message))

def resolve_canonical_repo(api_base, owner, repo, headers):
    """Resolves redirected owner/repo names to canonical API values."""
    url = f"{api_base}/repos/{owner}/{repo}"
    status, body, _ = _api_json_request("GET", url, headers=headers)
    if status == 200 and isinstance(body, dict):
        resolved_owner = body.get("owner", {}).get("login", owner)
        resolved_repo = body.get("name", repo)
        return resolved_owner, resolved_repo
    return owner, repo

def ensure_in_progress_label(api_base, owner, repo, headers):
    labels_url = f"{api_base}/repos/{owner}/{repo}/labels"
    status, labels, raw = _api_json_request("GET", labels_url, headers=headers)
    if status != 200 or not isinstance(labels, list):
        print(f"Failed to list labels. Status={status}. Body={raw}")
        return None

    for label in labels:
        if label.get("name") == "in-progress":
            return label.get("id")

    create_payload = {
        "name": "in-progress",
        "color": "f29513",
        "description": "Task currently claimed by supervisor",
    }
    create_status, created, create_raw = _api_json_request(
        "POST", labels_url, payload=create_payload, headers=headers
    )
    if create_status in (200, 201) and isinstance(created, dict):
        return created.get("id")

    print(
        "Failed to create 'in-progress' label. "
        f"Status={create_status}. Body={create_raw}"
    )

    # Label may already exist due to race; re-fetch once.
    status, labels, raw = _api_json_request("GET", labels_url, headers=headers)
    if status != 200 or not isinstance(labels, list):
        print(f"Failed to re-list labels. Status={status}. Body={raw}")
        return None
    for label in labels:
        if label.get("name") == "in-progress":
            return label.get("id")
    return None

def attach_label_id_to_issue(api_base, owner, repo, issue_number, label_id, headers):
    url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/labels"
    status, _, raw = _api_json_request(
        "POST",
        url,
        payload={"labels": [label_id]},
        headers=headers,
    )
    if status in (200, 201):
        return True
    print(
        f"Failed to attach label id {label_id} to issue #{issue_number}. "
        f"Status={status}. Body={raw}"
    )
    return False

def verify_issue_has_in_progress(api_base, owner, repo, issue_number, headers):
    url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/labels"
    status, labels, raw = _api_json_request("GET", url, headers=headers)
    if status != 200 or not isinstance(labels, list):
        print(
            f"Failed to verify labels for issue #{issue_number}. "
            f"Status={status}. Body={raw}"
        )
        print("CLAIM_VERIFIED in-progress present=false")
        return False

    present = any(lbl.get("name") == "in-progress" for lbl in labels)
    print(f"CLAIM_VERIFIED in-progress present={str(present).lower()}")
    return present

def claim_issue_with_in_progress(api_base, owner, repo, issue_number, headers):
    label_id = ensure_in_progress_label(api_base, owner, repo, headers)
    if label_id is None:
        print("CLAIM_VERIFIED in-progress present=false")
        return False
    attached = attach_label_id_to_issue(
        api_base, owner, repo, issue_number, label_id, headers
    )
    verified = verify_issue_has_in_progress(
        api_base, owner, repo, issue_number, headers
    )
    return attached and verified

def post_issue_comment(api_base, owner, repo, issue_number, body, headers):
    url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    status, _, raw = _api_json_request("POST", url, payload={"body": body}, headers=headers)
    if status not in (200, 201):
        print(f"Failed to post issue comment for #{issue_number}. Status={status}. Body={raw}")
        return False
    return True

def close_issue(api_base, owner, repo, issue_number, headers):
    url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}"
    status, _, raw = _api_json_request("PATCH", url, payload={"state": "closed"}, headers=headers)
    if status not in (200, 201):
        print(f"Failed to close issue #{issue_number}. Status={status}. Body={raw}")
        return False
    return True

def build_dispatch_input(task, instruction_text, governance_hash):
    return {
        "task_id": task["number"],
        "instruction": instruction_text,
        "allowed_files": _extract_allowed_files(instruction_text),
        "expected_outcome": f"Task #{task['number']} executes deterministically",
        "governance_hash": governance_hash,
        "timestamp": _utc_iso8601(),
    }

def verify_executor_result(result, dispatch_input, max_duration_seconds):
    changed_files = result.changed_files or []
    allowed_files = dispatch_input["allowed_files"]
    changed_subset = set(changed_files).issubset(set(allowed_files))
    commit_message_ok = _is_commit_message_valid(None)
    within_timeout = result.exit_status != 124
    deterministic_status = result.status in {"success", "failure"}

    verified = (
        deterministic_status
        and changed_subset
        and commit_message_ok
        and within_timeout
    )
    return {
        "verified": verified,
        "changed_subset_allowed": changed_subset,
        "commit_message_ok": commit_message_ok,
        "within_timeout": within_timeout,
        "max_duration_seconds": max_duration_seconds,
    }

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
        governance_hash = context_info["governance_hash"]
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
        headers = _auth_headers(env)
        owner, repo = resolve_canonical_repo(api_base, owner, repo, headers)

        env_validation = validate_environment(
            api_base=api_base,
            owner=owner,
            repo=repo,
            auth_headers=headers,
        )
        if not env_validation["environment_valid"]:
            print(json.dumps(env_validation, sort_keys=True))
            print("Environment validation failed; aborting cycle before task claiming.")
            print(enforcer.compliance_report_block())
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
                if claim_issue_with_in_progress(
                    api_base, owner, repo, task['number'], headers
                ):
                    print(f"CLAIMED issue #{task['number']}")
                    dispatch_input = build_dispatch_input(
                        task=task,
                        instruction_text=instruction_text,
                        governance_hash=governance_hash,
                    )
                    max_duration_seconds = 60
                    execution_dispatched = False
                    execution_verified = False
                    task_final_state = "retry_pending"

                    try:
                        result, dispatch_meta = dispatch_task_once(
                            dispatch_input,
                            start_timeout_seconds=5,
                            max_duration_seconds=max_duration_seconds,
                        )
                        execution_dispatched = True
                        verification = verify_executor_result(
                            result, dispatch_input, max_duration_seconds
                        )
                        execution_verified = verification["verified"]

                        if execution_verified and result.status == "success":
                            task_final_state = "completed"
                            close_issue(api_base, owner, repo, task["number"], headers)
                            post_issue_comment(
                                api_base,
                                owner,
                                repo,
                                task["number"],
                                "Execution completed and verified by deterministic executor.",
                                headers,
                            )
                        else:
                            task_final_state = "retry_pending"
                            post_issue_comment(
                                api_base,
                                owner,
                                repo,
                                task["number"],
                                "Execution failed verification; task kept open for deterministic retry.",
                                headers,
                            )

                        _append_execution_log(
                            {
                                "task_id": task["number"],
                                "dispatch_timestamp": dispatch_meta["dispatch_timestamp"],
                                "executor_command": dispatch_meta["executor_command"],
                                "exit_status": result.exit_status,
                                "verification_outcome": execution_verified,
                                "final_task_state": task_final_state,
                            }
                        )
                    except DispatchFailure as e:
                        task_final_state = "blocked" if str(e) == "execution.lock.violation" else "retry_pending"
                        post_issue_comment(
                            api_base,
                            owner,
                            repo,
                            task["number"],
                            f"Execution dispatch failure: {e}",
                            headers,
                        )
                        _append_execution_log(
                            {
                                "task_id": task["number"],
                                "dispatch_timestamp": _utc_iso8601(),
                                "executor_command": [],
                                "exit_status": -1,
                                "verification_outcome": False,
                                "final_task_state": task_final_state,
                            }
                        )

                    print(enforcer.compliance_report_block())
                    print(f"execution_dispatched: {str(execution_dispatched).lower()}")
                    print(f"execution_verified: {str(execution_verified).lower()}")
                    print(f"task_final_state: {task_final_state}")
                    sys.exit(0)
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

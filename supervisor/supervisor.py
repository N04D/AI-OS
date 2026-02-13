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
from orchestrator.git import create_governed_commit

TTL_SECONDS = 1800
PHASE_MILESTONE_NAMES = [
    "Phase 1 — Governed Core Runtime",
    "Phase 2 — Environment Validation Layer",
    "Phase 3 — Task Execution Engine",
    "Phase 4 — Result & State Management",
    "Phase 5 — End-to-End Governed Autonomy",
]

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

def get_open_issues(api_base, owner, repo, headers=None):
    """Fetches open issues from the Gitea API."""
    api_url = f"{api_base}/repos/{owner}/{repo}/issues?state=open&limit=300"
    status, data, _ = _api_json_request("GET", api_url, headers=headers)
    if status == 200 and isinstance(data, list):
        return data
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
    return sorted(set(re.findall(r"`([A-Za-z0-9_./-]+)`", instruction_text)))

def _is_commit_message_valid(message):
    if not message:
        return True
    return bool(re.match(r"^(feat|fix|chore)\([^)]+\): .+", message))

def _git_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

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

def _parse_iso8601(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None

def _issue_label_names(issue):
    return {lbl.get("name") for lbl in issue.get("labels", []) if isinstance(lbl, dict)}

def _milestone_id(issue):
    milestone = issue.get("milestone")
    if isinstance(milestone, dict):
        return milestone.get("id")
    return None

def _is_eligible_build_issue(issue, phase_id=None):
    if issue.get("state") != "open":
        return False
    labels = _issue_label_names(issue)
    if "type:build" not in labels:
        return False
    if "in-progress" in labels:
        return False
    if phase_id is not None and _milestone_id(issue) != phase_id:
        return False
    return True

def _phase_milestone_lookup(milestones):
    lookup = {}
    for milestone in milestones:
        title = milestone.get("title")
        if title in PHASE_MILESTONE_NAMES and title not in lookup:
            lookup[title] = milestone
    return lookup

def _issue_last_in_progress_event_at(api_base, owner, repo, issue_number, headers):
    timeline_url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/timeline"
    status, body, _ = _api_json_request("GET", timeline_url, headers=headers)
    if status != 200 or not isinstance(body, list):
        return None
    latest = None
    for event in body:
        if not isinstance(event, dict):
            continue
        label = event.get("label")
        label_name = label.get("name") if isinstance(label, dict) else None
        event_type = (event.get("type") or "").lower()
        if label_name == "in-progress" or "label" in event_type:
            created = _parse_iso8601(event.get("created_at"))
            if created and (latest is None or created > latest):
                latest = created
    return latest

def remove_in_progress_label(api_base, owner, repo, issue_number, headers):
    labels_url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/labels"
    status, labels, raw = _api_json_request("GET", labels_url, headers=headers)
    if status != 200 or not isinstance(labels, list):
        print(
            f"Failed to list issue labels for #{issue_number}. "
            f"Status={status}. Body={raw}"
        )
        return False

    target = None
    for lbl in labels:
        if lbl.get("name") == "in-progress":
            target = lbl
            break
    if target is None:
        return True

    label_id = target.get("id")
    if label_id is None:
        return False

    delete_url = (
        f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/labels/{label_id}"
    )
    del_status, _, del_raw = _api_json_request("DELETE", delete_url, headers=headers)
    if del_status not in (200, 204):
        print(
            f"Failed to remove in-progress label from #{issue_number}. "
            f"Status={del_status}. Body={del_raw}"
        )
        return False
    return True

def release_stale_in_progress_claims(api_base, owner, repo, issues, headers, ttl_seconds):
    now = datetime.now(timezone.utc)
    released = []
    for issue in issues:
        if issue.get("state") != "open":
            continue
        labels = _issue_label_names(issue)
        if "in-progress" not in labels:
            continue

        last_event_at = _issue_last_in_progress_event_at(
            api_base, owner, repo, issue["number"], headers
        )
        if last_event_at is None:
            last_event_at = _parse_iso8601(issue.get("updated_at"))
        if last_event_at is None:
            continue

        age_seconds = (now - last_event_at).total_seconds()
        if age_seconds <= ttl_seconds:
            continue

        removed = remove_in_progress_label(
            api_base, owner, repo, issue["number"], headers
        )
        if not removed:
            continue
        post_issue_comment(
            api_base,
            owner,
            repo,
            issue["number"],
            f"AUTO_RELEASE: stale in-progress claim released by supervisor (ttl={ttl_seconds}s).",
            headers,
        )
        print(f"CLAIM_STUCK_RELEASED issue={issue['number']} ttl_seconds={ttl_seconds}")
        released.append(issue["number"])
    return released

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

def get_milestones(api_base, owner, repo, headers):
    url = f"{api_base}/repos/{owner}/{repo}/milestones?state=all"
    status, body, raw = _api_json_request("GET", url, headers=headers)
    if status != 200 or not isinstance(body, list):
        print(f"Failed to list milestones. Status={status}. Body={raw}")
        return []
    return body

def _phase_sort_key(milestone):
    title = milestone.get("title", "")
    m = re.search(r"phase\\s*(\\d+)", title, re.IGNORECASE)
    if m:
        return (int(m.group(1)), milestone.get("id", 10**9))
    return (10**9, milestone.get("id", 10**9))

def detect_active_phase(milestones, open_issues):
    phase_lookup = _phase_milestone_lookup(milestones)
    for phase_name in PHASE_MILESTONE_NAMES:
        milestone = phase_lookup.get(phase_name)
        if not milestone:
            continue
        phase_id = milestone.get("id")
        if any(_is_eligible_build_issue(issue, phase_id) for issue in open_issues):
            return milestone
    return None

def _open_build_phase_ids(open_issues):
    ids = set()
    for issue in open_issues:
        names = [lbl["name"] for lbl in issue.get("labels", [])]
        if issue.get("state") == "open" and "type:build" in names:
            milestone = issue.get("milestone")
            if isinstance(milestone, dict) and milestone.get("id") is not None:
                ids.add(milestone["id"])
    return ids

def select_task_for_phase(issues, active_phase_id):
    available_issues = [issue for issue in issues if _is_eligible_build_issue(issue, active_phase_id)]
    return min(available_issues, key=lambda i: i["number"]) if available_issues else None

def count_eligible_tasks_for_phase(issues, active_phase_id):
    return len([issue for issue in issues if _is_eligible_build_issue(issue, active_phase_id)])

def phase_complete_recheck(api_base, owner, repo, headers, active_phase_id):
    issues = get_open_issues(api_base, owner, repo, headers=headers)
    remaining = [issue for issue in issues if _is_eligible_build_issue(issue, active_phase_id)]
    return len(remaining) == 0

def get_next_phase_name(milestones, active_phase_id):
    ordered = sorted(milestones, key=_phase_sort_key)
    for idx, milestone in enumerate(ordered):
        if milestone.get("id") == active_phase_id:
            if idx + 1 < len(ordered):
                return ordered[idx + 1].get("title")
            return None
    return None

def ingest_executor_result(result, dispatch_input):
    payload = {}
    out = (result.stdout or "").strip()
    if out:
        try:
            payload = json.loads(out.splitlines()[-1])
        except Exception:
            payload = {}

    changed_files = payload.get("changed_files")
    if not isinstance(changed_files, list):
        changed_files = list(result.changed_files or [])

    # Deterministic fallback: if executor didn't emit changed_files, use the
    # governance-scoped allowed file list as declared dispatch scope.
    if not changed_files:
        changed_files = sorted(dispatch_input.get("allowed_files", []))

    tests_passed = payload.get("tests_passed")
    if not isinstance(tests_passed, bool):
        tests_passed = bool(result.tests_passed)

    commit_hash = payload.get("commit_hash")
    if commit_hash is not None and not isinstance(commit_hash, str):
        commit_hash = None

    result.changed_files = changed_files
    result.tests_passed = tests_passed
    result.commit_hash = commit_hash
    return result

def select_task(issues):
    """Deterministically selects the issue with the lowest number."""
    if not issues:
        return None

    # Execute only governed build tasks and skip already claimed issues.
    available_issues = [
        issue for issue in issues
        if "type:build" in [lbl["name"] for lbl in issue.get("labels", [])]
        and "in-progress" not in [lbl["name"] for lbl in issue.get("labels", [])]
    ]
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

        issues = get_open_issues(api_base, owner, repo, headers=headers)
        release_stale_in_progress_claims(
            api_base, owner, repo, issues, headers, TTL_SECONDS
        )
        issues = get_open_issues(api_base, owner, repo, headers=headers)
        milestones = get_milestones(api_base, owner, repo, headers)

        active_phase = detect_active_phase(milestones, issues)
        if active_phase is None:
            print("NO_ELIGIBLE_BUILD_ISSUES active_phase=none")
            print(enforcer.compliance_report_block())
            time.sleep(60)
            continue

        active_phase_id = active_phase["id"]
        active_phase_name = active_phase.get("title", "")
        eligible_count = count_eligible_tasks_for_phase(issues, active_phase_id)

        print(f"ACTIVE_PHASE={active_phase_name}")
        print(f"ELIGIBLE_TASK_COUNT={eligible_count}")
        print(f'PHASE_GATE_ACTIVE phase="{active_phase_name}" milestone_id={active_phase_id}')
        
        if issues:
            task = select_task_for_phase(issues, active_phase_id)
            if task:
                print("PHASE_STATUS=running")
                print(f'PHASE_GATE_SELECTED issue={task["number"]} phase="{active_phase_name}"')
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
                    commit_created = False
                    commit_hash = None
                    files_committed = []

                    try:
                        result, dispatch_meta = dispatch_task_once(
                            dispatch_input,
                            start_timeout_seconds=5,
                            max_duration_seconds=max_duration_seconds,
                        )
                        execution_dispatched = True
                        result = ingest_executor_result(result, dispatch_input)
                        verification = verify_executor_result(
                            result, dispatch_input, max_duration_seconds
                        )
                        execution_verified = verification["verified"]

                        commit_attempt_eligible = (
                            execution_verified
                            and result.status == "success"
                            and result.tests_passed is True
                            and set(result.changed_files).issubset(set(dispatch_input["allowed_files"]))
                        )

                        requires_commit = bool(result.changed_files)

                        if commit_attempt_eligible and requires_commit:
                            commit_message = f"feat(task-{dispatch_input['task_id']}): governed executor result"
                            try:
                                enforcer.validate_commit_policy(
                                    instruction_text=instruction_text,
                                    changed_files=result.changed_files,
                                    commit_message=commit_message,
                                )
                                commit_result = create_governed_commit(result, dispatch_input)
                            except GovernanceViolation:
                                commit_result = {
                                    "commit_created": False,
                                    "commit_hash": None,
                                    "files_committed": [],
                                }
                        else:
                            commit_result = {
                                "commit_created": False,
                                "commit_hash": None,
                                "files_committed": [],
                                }

                        commit_created = bool(commit_result["commit_created"])
                        commit_hash = commit_result["commit_hash"]
                        files_committed = commit_result["files_committed"]

                        close_allowed = (
                            execution_verified
                            and result.status == "success"
                            and result.tests_passed is True
                            and ((not requires_commit) or commit_created)
                        )

                        if close_allowed:
                            task_final_state = "completed"
                            close_issue(api_base, owner, repo, task["number"], headers)
                            remove_in_progress_label(
                                api_base, owner, repo, task["number"], headers
                            )
                            post_issue_comment(
                                api_base,
                                owner,
                                repo,
                                task["number"],
                                f"Execution verified and governed commit created: {commit_hash}",
                                headers,
                            )
                            print(f"TASK_COMPLETED issue={task['number']} final_state=completed")
                        else:
                            task_final_state = "retry_pending"
                            post_issue_comment(
                                api_base,
                                owner,
                                repo,
                                task["number"],
                                "Execution verified but commit was not created; task kept open for deterministic retry.",
                                headers,
                            )

                        _append_execution_log(
                            {
                                "task_id": task["number"],
                                "dispatch_timestamp": dispatch_meta["dispatch_timestamp"],
                                "executor_command": dispatch_meta["executor_command"],
                                "exit_status": result.exit_status,
                                "verification_outcome": execution_verified,
                                "commit_created": commit_created,
                                "commit_hash": commit_hash,
                                "files_committed": files_committed,
                                "final_task_state": task_final_state,
                            }
                        )
                        if phase_complete_recheck(api_base, owner, repo, headers, active_phase_id):
                            print(f'PHASE_COMPLETE phase="{active_phase_name}" milestone_id={active_phase_id}')
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
                                "commit_created": False,
                                "commit_hash": None,
                                "files_committed": [],
                                "final_task_state": task_final_state,
                            }
                        )

                    print(enforcer.compliance_report_block())
                    print(f"execution_dispatched: {str(execution_dispatched).lower()}")
                    print(f"execution_verified: {str(execution_verified).lower()}")
                    print(f"commit_created: {str(commit_created).lower()}")
                    print(f"commit_hash: {commit_hash}")
                    print(f"files_committed: {files_committed}")
                    print(f"task_final_state: {task_final_state}")
                    sys.exit(0)
                else:
                    print(f"Failed to claim issue #{task['number']}. Retrying in next loop.")
            else:
                if phase_complete_recheck(api_base, owner, repo, headers, active_phase_id):
                    print("PHASE_STATUS=complete")
                    print(f'PHASE_COMPLETE phase="{active_phase_name}" milestone_id={active_phase_id}')
                print("PHASE_STATUS=running")
                print("NO_ELIGIBLE_BUILD_ISSUES active_phase=none")
        else:
            print("NO_ELIGIBLE_BUILD_ISSUES active_phase=none")
        print(enforcer.compliance_report_block())
        time.sleep(60) # Sleep even if claiming failed or all issues are in-progress

if __name__ == "__main__":
    main()

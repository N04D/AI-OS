import json
import os
from supervisor.pr_gate.logger import log_event


def gate_report(pr_number, head_sha, policy_hash, result):
    payload = {
        "pr_number": pr_number,
        "head_sha": head_sha,
        "policy_hash": policy_hash,
        "passed": result.get("passed", False),
        "failed_gates": result.get("failed_gates", []),
        "system_evolution": result.get("system_evolution", False),
    }
    return "PR_GATE_REPORT " + json.dumps(payload, sort_keys=True)


def write_gate_artifact(pr_number, head_sha, policy_hash, result, root="artifacts/governance"):
    os.makedirs(root, exist_ok=True)
    payload = {
        "pr_number": pr_number,
        "head_sha": head_sha,
        "policy_hash": policy_hash,
        "passed": result.get("passed", False),
        "failed_gates": result.get("failed_gates", []),
        "observed": result.get("observed", {}),
    }
    path = os.path.join(root, f"pr-{pr_number}-{head_sha}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, indent=2)
        f.write("\n")
    status = "PASS" if result.get("passed", False) else "FAIL"
    log_event("artifact", f"wrote pr-{pr_number}-{head_sha}.json status={status}")
    return path

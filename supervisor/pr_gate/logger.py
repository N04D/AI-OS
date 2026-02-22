import os
import re
from datetime import datetime, timezone


DEFAULT_LOG_PATH = "governance/logs/pr-gate.log"


def _log_path():
    return os.environ.get("PR_GATE_LOG_PATH", DEFAULT_LOG_PATH)


def _sanitize(text):
    value = str(text)
    value = re.sub(r"(?i)authorization\s*[:=]\s*[^\s,;]+", "Authorization=[REDACTED]", value)
    value = re.sub(r"(?i)\b(token|bearer)\s+[A-Za-z0-9._\-]+", r"\1 [REDACTED]", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def log_event(component: str, message: str) -> None:
    path = _log_path()
    line = (
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"[{_sanitize(component)}] {_sanitize(message)}"
    )
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        return


def dry_run_log() -> str:
    from supervisor.pr_gate.evaluator import evaluate_pr
    from supervisor.pr_gate.report import write_gate_artifact

    policy = {
        "branch_rules": {
            "feature_to_develop_only": True,
            "patterns": {
                "feature": {"regex": r"^feature/.+$"},
                "hotfix": {"regex": r"^hotfix/.+$"},
                "release": {"regex": r"^release/.+$"},
            },
        },
        "approvals": {
            "disallow_self_approval": True,
            "develop": {"min_approvals": 1, "require_distinct_reviewer": True},
        },
        "issue_link": {"required": True, "patterns": [r"(^|\\s)#([0-9]+)(\\s|$)"]},
        "pr_template": {
            "required_sections": ["Subsystem", "Risk Level"],
            "reject_placeholders": ["TBD", "TODO", "N/A"],
            "min_section_length": 2,
        },
        "high_risk_paths": ["supervisor/"],
        "locks": {
            "required_on_high_risk": True,
            "exclusive": True,
            "allowed": ["LOCK:supervisor/"],
        },
        "ci": {"required_checks": ["lint", "unit-tests"]},
        "system_evolution": {
            "detect_paths": ["supervisor/", "governance/policy/"],
            "approvals": {"min_approvals": 2, "require_human_approval": True},
            "ci": {"required_checks": ["lint", "unit-tests", "determinism-check"]},
        },
        "commit_signing": {"required": True},
    }
    pr = {
        "number": 999,
        "title": "feature work #123",
        "body": "### Subsystem\ncore\n### Risk Level\nhigh\nLOCK:supervisor/",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/demo"},
        "user": {"login": "author"},
        "_open_prs": [],
    }
    commits = [{"sha": "dryrunsha", "signature_verifiable": True, "signature_verified": True}]
    files = ["supervisor/supervisor.py"]
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "reviewer", "type": "User"}}]
    statuses = [{"context": "lint", "state": "success"}, {"context": "unit-tests", "state": "success"}]

    result = evaluate_pr(policy, pr, commits, files, reviews, statuses)
    for gate in result.get("gate_events", []):
        log_event(
            "evaluate_pr",
            f"gate={gate.get('gate')} result={gate.get('result')} reason={gate.get('reason')}",
        )
    log_event(
        "evaluate_pr",
        f"FINAL result={'PASS' if result.get('passed', False) else 'FAIL'} failed_gates={result.get('failed_gates', [])}",
    )
    write_gate_artifact(999, "dryrunsha", "0" * 64, result)
    log_event("status_publish", "context=supervisor/governance state=pending sha=dryrunsha http=200")
    return _log_path()

from llm import generate_commit_summary, format_commit_message
from git import get_diff, get_changed_files, create_branch, commit, push
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor.governance_enforcement import GovernanceEnforcer, GovernanceViolation

def handle_success(task_id, task_text, eval_log):
    enforcer = GovernanceEnforcer(
        governance_path="docs/governance.md",
        environment_path="agents/state/environment.json",
    )
    enforcer.load_context()
    enforcer.validate_pre_computation(
        instruction_text=task_text,
        intended_outcome=f"Create and push commit for task {task_id}",
    )

    diff = get_diff()

    summary = generate_commit_summary(task_text, eval_log, diff)
    commit_msg = format_commit_message(summary, task_id)
    changed_files = get_changed_files()
    try:
        enforcer.validate_commit_policy(task_text, changed_files, commit_msg)
    except GovernanceViolation:
        print(enforcer.compliance_report_block())
        raise

    branch = create_branch(task_id)
    commit(commit_msg)
    push(branch)

    print(f"Committed and pushed feature branch: {branch}")
    print(enforcer.compliance_report_block())

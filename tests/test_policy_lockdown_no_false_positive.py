from supervisor.pr_gate.policy_loader import load_policy
from supervisor.supervisor import enforce_policy_hash_lockdown


def test_policy_lockdown_no_false_positive(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_GATE_LOG_PATH", str(tmp_path / "pr-gate.log"))
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        "\n".join(
            [
                'version: "v0.2"',
                "branch_rules: {}",
                "approvals: {}",
                "high_risk_paths: []",
                "commit_signing: {required: false}",
                "ci: {required_checks: []}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PR_GATE_POLICY_PATH", str(policy_file))

    _, baseline = load_policy(str(policy_file))
    current = enforce_policy_hash_lockdown(baseline)
    assert current == baseline

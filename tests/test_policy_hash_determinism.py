from supervisor.pr_gate.policy_loader import load_policy


def test_policy_hash_stable_then_changes(tmp_path, monkeypatch):
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

    _, hash1 = load_policy(str(policy_file))
    _, hash2 = load_policy(str(policy_file))
    assert hash1 == hash2

    policy_file.write_text(
        "\n".join(
            [
                'version: "v0.2"',
                "branch_rules: {feature_to_develop_only: true}",
                "approvals: {}",
                "high_risk_paths: []",
                "commit_signing: {required: false}",
                "ci: {required_checks: []}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _, hash3 = load_policy(str(policy_file))
    assert hash3 != hash1

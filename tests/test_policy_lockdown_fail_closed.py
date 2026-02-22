import pytest

from supervisor.pr_gate.policy_loader import load_policy
from supervisor.supervisor import enforce_policy_hash_lockdown


def test_policy_lockdown_raises_on_hash_change(tmp_path, monkeypatch):
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

    with pytest.raises(RuntimeError) as exc:
        enforce_policy_hash_lockdown(baseline)

    msg = str(exc.value)
    assert "POLICY_LOCKDOWN" in msg
    assert f"baseline={baseline}" in msg
    assert "current=" in msg

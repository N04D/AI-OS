import textwrap

import pytest

from supervisor.pr_gate.policy_loader import PolicyLoadError, load_policy


def test_policy_loader_valid(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_GATE_LOG_PATH", str(tmp_path / "pr-gate.log"))
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        textwrap.dedent(
            """
            version: "v0.2"
            branch_rules: {}
            approvals: {}
            high_risk_paths: []
            commit_signing: {required: false}
            ci: {required_checks: []}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    policy, policy_hash = load_policy(str(policy_file))
    assert policy["version"] == "v0.2"
    assert len(policy_hash) == 64


def test_policy_loader_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("PR_GATE_LOG_PATH", str(tmp_path / "pr-gate.log"))
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("version: v0.2\n", encoding="utf-8")

    with pytest.raises(PolicyLoadError):
        load_policy(str(policy_file))

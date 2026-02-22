import json

from supervisor.pr_gate.report import write_gate_artifact


def test_artifact_write(tmp_path):
    out = write_gate_artifact(
        pr_number=7,
        head_sha="abc123",
        policy_hash="f" * 64,
        result={"passed": False, "failed_gates": ["required_status_checks"], "observed": {"x": 1}},
        root=str(tmp_path),
    )
    with open(out, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["pr_number"] == 7
    assert payload["head_sha"] == "abc123"
    assert payload["failed_gates"] == ["required_status_checks"]

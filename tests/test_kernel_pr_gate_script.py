import hashlib
import json
from pathlib import Path

from scripts.kernel_pr_gate import main


def _baseline_hash() -> str:
    files = [
        "governance/policy/pr-governance.v0.2.yaml",
        "governance/policy/kernel-enforcement-checklist.v0.1.yaml",
    ]
    pairs = []
    for rel in files:
        pairs.append((rel, hashlib.sha256(Path(rel).read_bytes()).hexdigest()))
    raw = json.dumps({"files": pairs}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_kernel_pr_gate_fixture_mode_allows(tmp_path):
    pr_path = tmp_path / "pr.json"
    extra_path = tmp_path / "extra.json"
    out_path = tmp_path / "verdict.json"
    pr_path.write_text(
        json.dumps(
            {
                "head": {"ref": "feat/kernel-check"},
                "user": {"login": "codex"},
                "body": (
                    "intent_id: I-1\n"
                    "issue_reference: #65\n"
                    "risk_level: L3\n"
                    "touched_paths: supervisor/pr_gate/kernel_enforcer.py\n"
                    "rollback_strategy: revert\n"
                    "determinism_proof: pytest -q\n"
                ),
            }
        ),
        encoding="utf-8",
    )
    extra_path.write_text(
        json.dumps(
            {
                "files": ["supervisor/pr_gate/kernel_enforcer.py"],
                "reviews": [{"state": "APPROVED", "user": {"login": "reviewer"}}],
                "statuses": [
                    {"context": "lint", "state": "success"},
                    {"context": "unit-tests", "state": "success"},
                    {"context": "smoke-test", "state": "success"},
                ],
                "escalation_level": "L3",
                "owner_approved": True,
                "toolchain": {
                    "python_version": "3.11.9",
                    "dependency_lock_sha": "abc",
                    "ci_runtime_fingerprint": "runner",
                },
                "mirror": {"canonical_main_sha": "abc", "mirror_main_sha": "abc"},
            }
        ),
        encoding="utf-8",
    )
    exit_code = main(
        [
            "--pr-json",
            str(pr_path),
            "--extra-json",
            str(extra_path),
            "--governance-baseline-hash",
            _baseline_hash(),
            "--output",
            str(out_path),
        ]
    )
    assert exit_code == 0
    verdict = json.loads(out_path.read_text(encoding="utf-8"))
    assert verdict["allow"] is True


def test_kernel_pr_gate_requires_api_or_fixtures(tmp_path):
    out_path = tmp_path / "verdict.json"
    exit_code = main(
        [
            "--governance-baseline-hash",
            "x",
            "--output",
            str(out_path),
        ]
    )
    assert exit_code == 1
    verdict = json.loads(out_path.read_text(encoding="utf-8"))
    assert verdict["allow"] is False
    assert verdict["reason_code"] == "DENY_MISSING_API_INPUT"

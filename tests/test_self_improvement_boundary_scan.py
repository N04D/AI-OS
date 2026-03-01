from __future__ import annotations

from supervisor.pr_gate.evaluator import _scan_self_improvement_boundary


def test_boundary_scan_is_deterministic_and_sorted() -> None:
    files = ["tests/test_a.py", "supervisor/z.py", "docs/x.md", "governance/policy.yaml"]
    first = _scan_self_improvement_boundary(files, ["supervisor/"], "MED")
    second = _scan_self_improvement_boundary(list(reversed(files)), ["supervisor/"], "MED")
    assert first == second
    assert first["disallowed_paths"] == ["governance/policy.yaml"]


def test_boundary_scan_detects_runtime_without_tests() -> None:
    scan = _scan_self_improvement_boundary(
        ["supervisor/refactor.py"],
        ["supervisor/"],
        "MED",
    )
    assert scan["runtime_changed"] == ["supervisor/refactor.py"]
    assert scan["tests_changed"] is False


def test_boundary_scan_governance_core_detection() -> None:
    scan = _scan_self_improvement_boundary(
        ["governance/policy/x.yaml", "tests/test_x.py"],
        [],
        "LOW",
    )
    assert scan["touched_governance_core"] == ["governance/policy/x.yaml"]

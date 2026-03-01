from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_PATH = REPO_ROOT / "supervisor" / "control_plane.py"


def _is_runtime_python(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    rel = path.relative_to(REPO_ROOT)
    if rel.parts[0] in {"tests"}:
        return False
    if rel.parts[0] == "autonomy_budget":
        return False
    if rel.parts[0] == "supervisor" and len(rel.parts) > 1 and rel.parts[1] == "tests":
        return False
    return True


def _imports_for(path: Path) -> list[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                out.append((node.module, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, "*"))
    return out


def test_governance_core_imports_are_confined_to_control_plane() -> None:
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*.py"):
        if not _is_runtime_python(path):
            continue
        if path == CONTROL_PLANE_PATH:
            continue
        rel = path.relative_to(REPO_ROOT)
        for module, name in _imports_for(path):
            if module == "autonomy_budget.engine":
                violations.append(f"{rel}: imports autonomy_budget.engine directly")
            if module == "supervisor.budgets" and name == "consume_from_path":
                violations.append(f"{rel}: imports supervisor.budgets.consume_from_path directly")
            if module == "supervisor.scheduler" and name in {
                "load_scheduler_config",
                "load_scheduler_state",
                "compute_due_jobs",
                "dispatch_task",
            }:
                violations.append(f"{rel}: imports supervisor.scheduler.{name} directly")
            if module == "supervisor.autonomy_task_materializer" and name == "materialize_autonomy_tasks":
                violations.append(f"{rel}: imports materialize_autonomy_tasks directly")

    assert violations == []


def test_executor_cannot_import_budget_core() -> None:
    violations: list[str] = []
    for path in (REPO_ROOT / "executor").rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        for module, name in _imports_for(path):
            if module in {"autonomy_budget.engine", "supervisor.budgets"}:
                violations.append(f"{rel}: imports {module}")
            if module == "autonomy_budget" and name in {"BudgetEngine", "BudgetError"}:
                violations.append(f"{rel}: imports autonomy_budget.{name}")
    assert violations == []

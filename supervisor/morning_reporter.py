from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from supervisor.skill_linter import lint_skill_roots


@dataclass(frozen=True)
class Idea:
    idx: int
    category: str
    title: str
    why: str
    impact: str
    acceptance: str
    score: int
    first_step: str


@dataclass(frozen=True)
class ActionItem:
    task: str
    goal: str
    command: str
    check: str


def _load_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _violations_count(payload: dict[str, Any]) -> int:
    violations = payload.get("violations")
    if isinstance(violations, list):
        return len(violations)
    if isinstance(violations, int) and violations >= 0:
        return violations
    return 0


def _build_ideas(tasks_executed: int, tasks_failed: int, violations: int) -> list[Idea]:
    boost_test = 2 if tasks_failed > 0 or violations > 0 else 0
    boost_ops = 2 if tasks_executed == 0 else 0
    return [
        Idea(
            1,
            "Skills",
            "Skill-linter uitbreiden met link-depth checks",
            "Voorkomt verborgen referentiefouten in grotere skill-sets.",
            "Hogere betrouwbaarheid van skill-instructies voordat night-run start.",
            "Linter markeert ontbrekende 2e-lijns references als waarschuwing/fout.",
            8 + boost_ops,
            "Voeg optionele `--strict-links` mode toe in `supervisor/skill_linter.py`.",
        ),
        Idea(
            2,
            "Skills",
            "Skill-index manifest per ochtendrun",
            "Maakt wijzigingen in actieve skills direct zichtbaar in rapport.",
            "Sneller triage bij regressies na skill-updates.",
            "Rapport bevat tabel met skill-naam, pad en lint-status.",
            7,
            "Genereer `workspace/codex/night/skill_index.json` vanuit lint-resultaten.",
        ),
        Idea(
            3,
            "Modules",
            "Night-run reporter module (uitgebreid)",
            "Eén centrale render-laag voorkomt drift tussen scripts en rapportformat.",
            "Consistente, leesbare ochtendrapporten met vaste kwaliteitschecks.",
            "Rapportgenerator levert exact 5 verplichte secties plus extra contextregels.",
            10 + boost_ops,
            "Koppel alle report-output via `supervisor/morning_reporter.py`.",
        ),
        Idea(
            4,
            "Modules",
            "Run-history trend samenvatter",
            "Laat direct zien of metrics verbeteren of verslechteren over dagen.",
            "Betere prioritering op basis van trend i.p.v. losse snapshots.",
            "Top van rapport toont 3-daagse trend voor executed/failed/violations.",
            8,
            "Lees laatste N files uit `logs/control/night_runs` en bereken delta's.",
        ),
        Idea(
            5,
            "Modules",
            "Actie-items generator voor ochtendtest",
            "Zet rapport direct om in testbare taken voor dezelfde dag.",
            "Kortere feedback-loop tussen rapport en implementatie.",
            "Rapport bevat minimaal 3 concrete testtaken met doel en check.",
            8 + boost_ops,
            "Maak helper die uit top-ideeën een compacte tasklist rendert.",
        ),
        Idea(
            6,
            "Kernel",
            "Config preflight voor night entrypoint",
            "Voorkomt runs met halfgeldige configuratie en onduidelijke fouten.",
            "Minder mislukte runs door vroege en duidelijke validatie.",
            "Entrypoint faalt vroeg met gerichte foutcode bij missende verplichte env.",
            7 + boost_test,
            "Voeg preflight-check functie toe vóór `aiosctl night-run`.",
        ),
        Idea(
            7,
            "Kernel",
            "Run-lock met conflictmelding",
            "Voorkomt dubbele of overlappende night-runs.",
            "Stabielere state en minder race conditions.",
            "Tweede run in zelfde window stopt met expliciete lock-reason.",
            7 + boost_test,
            "Maak lockfile protocol in `tools/night_mode_systemd_entry.sh`.",
        ),
        Idea(
            8,
            "Test/Infra",
            "JSON schema contracttest op night summary",
            "Beschermt alle rapportconsumenten tegen format regressies.",
            "Breuken zichtbaar in CI in plaats van ochtendverrassingen.",
            "Test faalt op ontbrekende keys of verkeerde types in summary JSON.",
            9 + boost_test,
            "Draai schema-validatie test op nieuwste summary fixtures.",
        ),
        Idea(
            9,
            "Test/Infra",
            "Snapshot tests voor morning report output",
            "Bewaakt lay-out, sectienamen en nummering op regressies.",
            "Rapport blijft consistent voor dagelijkse review.",
            "Snapshot test detecteert elke ongewenste formatwijziging.",
            9 + boost_test,
            "Voeg fixture en snapshot test toe voor `generate_report` output.",
        ),
        Idea(
            10,
            "Test/Infra",
            "E2E smoke: night-run naar rapport naar mail",
            "Valideert complete keten in één testflow.",
            "Snelle zekerheid dat rapport ook echt bij operator terechtkomt.",
            "Smoke test produceert rapport en een verzonden outbox item.",
            8 + boost_test,
            "Maak CI-script dat entrypoint + report + outbox verzending controleert.",
        ),
    ]


def _health_label(tasks_failed: int, violations: int) -> str:
    if tasks_failed == 0 and violations == 0:
        return "groen"
    if tasks_failed <= 1 and violations <= 1:
        return "oranje"
    return "rood"


def _command_for_idea(*, idea: Idea, summary_path: Path, linter_root: Path | None) -> str:
    lint_root = linter_root or (Path.home() / ".codex" / "skills")
    report_out = Path("workspace/codex/night/reports/morning_test_preview.md")
    validator = Path("workspace/codex/night/tools/validate_morning_report.py")
    if idea.idx == 1:
        return f"python3 tools/skill_linter.py --root {lint_root} --link-depth 2 --strict-links"
    if idea.idx == 5:
        return (
            "python3 -m supervisor.morning_reporter "
            f"--summary-path {summary_path} --night-status ok --linter-root {lint_root} "
            f"--output {report_out} && python3 {validator} {report_out}"
        )
    return "pytest -q tests/test_morning_reporter.py tests/test_skill_linter.py"


def _generate_action_items(
    *,
    top3: list[Idea],
    favorite: Idea,
    summary_path: Path,
    linter_root: Path | None,
) -> list[ActionItem]:
    selected = [idea for idea in top3 if idea.idx != favorite.idx][:2]
    action_items: list[ActionItem] = []
    for idea in selected:
        action_items.append(
            ActionItem(
                task=f"Implementeer idee {idea.idx}: [{idea.category}] {idea.title}",
                goal=idea.impact,
                command=_command_for_idea(idea=idea, summary_path=summary_path, linter_root=linter_root),
                check=idea.acceptance,
            )
        )

    action_items.append(
        ActionItem(
            task="Draai gerichte regressietests voor report + linter",
            goal="Bevestigen dat ochtendrapport en link-depth linting stabiel blijven.",
            command="pytest -q tests/test_morning_reporter.py tests/test_skill_linter.py",
            check="Pytest toont alle geselecteerde tests als geslaagd.",
        )
    )
    return action_items


def generate_report(
    *,
    summary: dict[str, Any],
    summary_path: Path,
    night_status: str,
    linter_root: Path | None = None,
    linter_link_depth: int = 2,
    linter_strict_links: bool = False,
) -> str:
    epoch = str(summary.get("epoch", "onbekend"))
    tasks_executed = int(summary.get("tasks_executed", 0) or 0)
    tasks_skipped = int(summary.get("tasks_skipped", 0) or 0)
    tasks_failed = int(summary.get("tasks_failed", 0) or 0)
    budget_used = float(summary.get("budget_used", 0) or 0)
    violations = _violations_count(summary)
    health = _health_label(tasks_failed, violations)

    skill_lint_line = "- Skill-linter: niet uitgevoerd."
    if linter_root is not None:
        lint_results = lint_skill_roots(
            [linter_root],
            link_depth=max(1, int(linter_link_depth)),
            strict_links=bool(linter_strict_links),
        )
        if lint_results:
            skills_total = len(lint_results)
            skills_with_issues = sum(0 if result.ok else 1 for result in lint_results)
            error_count = sum(result.error_count for result in lint_results)
            warning_count = sum(result.warning_count for result in lint_results)
            issue_count = error_count + warning_count
            skill_lint_line = (
                f"- Skill-linter: `skills={skills_total}`, `skills_with_issues={skills_with_issues}`, "
                f"`issues={issue_count}`, `errors={error_count}`, `warnings={warning_count}`, "
                f"`link_depth={max(1, int(linter_link_depth))}`, "
                f"`strict_links={bool(linter_strict_links)}` (root: `{linter_root}`)."
            )

    ideas = _build_ideas(tasks_executed, tasks_failed, violations)
    favorite = max(ideas, key=lambda idea: (idea.score, -idea.idx))
    top3 = sorted(ideas, key=lambda idea: (idea.score, -idea.idx), reverse=True)[:3]
    action_items = _generate_action_items(
        top3=top3,
        favorite=favorite,
        summary_path=summary_path,
        linter_root=linter_root,
    )

    lines: list[str] = []
    lines.append("**Night-run Resultaat**")
    lines.append(f"- Status: **{night_status or 'unknown'}**")
    lines.append(
        "- Kernmetrics: "
        f"`tasks_executed={tasks_executed}`, `tasks_skipped={tasks_skipped}`, "
        f"`tasks_failed={tasks_failed}`, `violations={violations}`."
    )
    lines.append(f"- Gezondheidslabel: **{health}**.")
    lines.append(f"- Bronbestand: `{summary_path}`.")
    lines.append(f"- Epoch: `{epoch}`.")
    lines.append(f"- Budget gebruikt: `{budget_used:g}`.")
    lines.append(skill_lint_line)
    lines.append("")

    lines.append("**Uitgevoerde Taken**")
    if tasks_executed <= 0:
        lines.append("- Er is expliciet niets uitgevoerd in deze night-run (`tasks_executed=0`).")
        lines.append("- Actiehint: controleer intake/scheduler als je wel werk verwachtte.")
    else:
        lines.append(f"- Uitgevoerd: `{tasks_executed}` taken.")
    if tasks_failed > 0:
        lines.append(f"- Fouten: `{tasks_failed}` (nader onderzoeken aanbevolen).")
    if violations > 0:
        lines.append(f"- Violations: `{violations}` (policy check vereist).")
    lines.append("")

    lines.append("**10 Ideeën Voor Vandaag**")
    for idea in ideas:
        lines.append(f"{idea.idx}. **[{idea.category}] {idea.title}**")
        lines.append(f"Waarom: {idea.why}")
        lines.append(f"Impact: {idea.impact}")
        lines.append(f"Acceptatiecheck: {idea.acceptance}")
        lines.append(f"Score: `{idea.score}`")
    lines.append("")

    lines.append("**Actie-items Voor Ochtendtest**")
    for idx, item in enumerate(action_items, start=1):
        lines.append(f"{idx}. Taak: {item.task}")
        lines.append(f"Doel: {item.goal}")
        lines.append(f"Command: `{item.command}`")
        lines.append(f"Check: {item.check}")
        lines.append("")

    lines.append("**Mijn Favoriet Om Nu Te Bouwen**")
    lines.append(f"- Gekozen idee: **{favorite.idx}. [{favorite.category}] {favorite.title}**")
    lines.append(
        "- Waarom nu beste keuze: "
        f"hoge score ({favorite.score}) op directe waarde en lage integratierisico's."
    )
    lines.append(f"- Eerste concrete implementatiestap in deze workspace: {favorite.first_step}")
    lines.append("")

    lines.append("**Aanbevolen Volgorde**")
    for rank, idea in enumerate(top3, start=1):
        lines.append(f"{rank}. **{idea.idx}. [{idea.category}] {idea.title}** (score `{idea.score}`)")

    return "\n".join(lines).strip() + "\n"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate extended morning night-run report")
    parser.add_argument("--summary-path", required=True)
    parser.add_argument("--night-status", default="unknown")
    parser.add_argument("--linter-root", default="")
    parser.add_argument("--linter-link-depth", type=int, default=2)
    parser.add_argument("--linter-strict-links", action="store_true")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary_path = Path(args.summary_path)
    summary = _load_summary(summary_path)
    linter_root = Path(args.linter_root).expanduser() if args.linter_root.strip() else None
    report = generate_report(
        summary=summary,
        summary_path=summary_path,
        night_status=str(args.night_status),
        linter_root=linter_root,
        linter_link_depth=max(1, int(args.linter_link_depth or 2)),
        linter_strict_links=bool(args.linter_strict_links),
    )
    if args.output.strip():
        out = Path(args.output)
        out.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

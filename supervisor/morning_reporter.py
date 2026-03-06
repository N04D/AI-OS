from __future__ import annotations

import argparse
import json
import re
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
    evidence: str


def _metric_from_summary(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_recent_trend(summary_path: Path, window: int = 3) -> str | None:
    summary_dir = summary_path.parent
    if not summary_dir.exists():
        return None

    rows: list[tuple[str, int, int, int]] = []
    for item in sorted(summary_dir.glob("*.json")):
        payload = _load_summary(item)
        epoch = str(payload.get("epoch", item.stem)).strip() or item.stem
        rows.append(
            (
                epoch,
                _metric_from_summary(payload, "tasks_executed"),
                _metric_from_summary(payload, "tasks_failed"),
                _violations_count(payload),
            )
        )
    if not rows:
        return None
    recent = rows[-max(1, int(window)) :]
    trend_bits = [
        f"{epoch}: executed={executed}, failed={failed}, violations={violations}"
        for epoch, executed, failed, violations in recent
    ]
    return " | ".join(trend_bits)


def _write_skill_index_manifest(*, lint_results: list[Any], output_path: Path) -> Path | None:
    if not lint_results:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "skills": [
            {
                "name": result.path.parent.name,
                "path": str(result.path),
                "ok": bool(result.ok),
                "errors": int(result.error_count),
                "warnings": int(result.warning_count),
            }
            for result in sorted(lint_results, key=lambda item: str(item.path))
        ]
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return output_path


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
        Idea(
            11,
            "Skills",
            "Skill changelog delta in ochtendrapport",
            "Maakt direct zichtbaar welke skills sinds gisteren aangepast zijn.",
            "Sneller beoordelen of skill-updates effect hebben op de run.",
            "Rapport toont lijst met gewijzigde skill-paden en wijzigingsmoment.",
            8,
            "Vergelijk skill-index van vandaag met vorige run en render alleen deltas.",
        ),
        Idea(
            12,
            "Skills",
            "Skill-coverage check op verplichte secties",
            "Voorkomt dat cruciale instructieblokken per ongeluk ontbreken.",
            "Hogere voorspelbaarheid van skillgedrag bij elke run.",
            "Linter faalt op ontbrekende verplichte sectiekoppen.",
            8,
            "Voeg verplichte sectie-validatie toe in skill-linter regelset.",
        ),
        Idea(
            13,
            "Modules",
            "Rapportdiff t.o.v. vorige run",
            "Laat in één oogopslag zien wat echt veranderd is.",
            "Minder tijd kwijt aan handmatig vergelijken van rapporten.",
            "Rapport bevat korte delta-sectie met changed/unchanged metrics.",
            9,
            "Laad vorige report en bereken compacte diff op kernsecties.",
        ),
        Idea(
            14,
            "Modules",
            "Prioriteitsscore met impact x effort matrix",
            "Maakt volgorde-bepaling expliciet en herhaalbaar.",
            "Betere keuzes voor wat als eerste gebouwd wordt.",
            "Top-3 bevat ook een score-opbouw per idee.",
            8,
            "Implementeer simpele matrixscore en toon factorbijdrage per idee.",
        ),
        Idea(
            15,
            "Modules",
            "Actieblokken met testcommando per voorstel",
            "Verlaagt drempel om direct te starten met bouwen/testen.",
            "Snellere omzetting van rapport naar uitvoering.",
            "Elk top-idee heeft direct uitvoerbaar commandoblok.",
            8,
            "Genereer per top-idee een command-template op basis van categorie.",
        ),
        Idea(
            16,
            "Kernel",
            "Night-run timeout guard per fase",
            "Voorkomt vastlopende runs zonder duidelijke stopconditie.",
            "Betrouwbaardere afhandeling bij trage subsystemen.",
            "Run stopt gecontroleerd met timeout-reason en fase-naam.",
            8,
            "Introduceer fase-timeouts en leg reden vast in run-output.",
        ),
        Idea(
            17,
            "Kernel",
            "Recovery-pad na gedeeltelijke runfouten",
            "Zorgt dat volgende run schoon kan hervatten na fouten.",
            "Minder handmatige interventie na incidenten.",
            "Na fout wordt recovery-state geschreven en volgende run leest die in.",
            8,
            "Maak recovery-state bestand en herstelstappen voor kritieke paden.",
        ),
        Idea(
            18,
            "Test/Infra",
            "Contracttest op mail-body structuur",
            "Voorkomt regressies in leesbaarheid van operator-mail.",
            "Stabiele mail-opmaak voor dagelijkse review.",
            "Test valideert verplichte mailsecties en kopvolgorde.",
            9,
            "Voeg parsercheck toe op gegenereerde mailbody uit entrypoint.",
        ),
        Idea(
            19,
            "Test/Infra",
            "Regression matrix voor lock/preflight paden",
            "Borgt dat nieuwe hardening niet ongemerkt stuk gaat.",
            "Minder risico op silent failures in cron-runs.",
            "Tests dekken success + conflict + preflight-fail paden.",
            9,
            "Breid tests uit met scenario-matrix voor night entrypoint.",
        ),
        Idea(
            20,
            "Test/Infra",
            "Dagelijkse smoke met artifact-validatie",
            "Combineert snelle health-check met bewijsartefacten.",
            "Direct zicht op end-to-end gezondheid van de keten.",
            "Smoke test schrijft rapportartifact en valide outbox-item.",
            9,
            "Plan smoke-script run en valide outputbestanden op vaste paden.",
        ),
    ]


def _load_completed_idea_ids(completed_dir: Path, epoch: str | None = None) -> set[int]:
    if not completed_dir.exists():
        return set()
    done: set[int] = set()
    pat = re.compile(r"_idea_(\d+)_done\.txt$")
    glob_pat = f"{epoch}_idea_*_done.txt" if epoch else "*_idea_*_done.txt"
    for item in completed_dir.glob(glob_pat):
        match = pat.search(item.name)
        if not match:
            continue
        try:
            done.add(int(match.group(1)))
        except ValueError:
            continue
    return done


def _load_lifecycle_state(path: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_items = payload.get("ideas")
    if not isinstance(raw_items, dict):
        return {}
    state: dict[str, dict[str, Any]] = {}
    for key, value in raw_items.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        state[key] = dict(value)
    return state


def _save_lifecycle_state(path: Path, state: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ideas": state}
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _status_for_idea(
    *,
    idea_id: int,
    completed_ids_any: set[int],
    state: dict[str, dict[str, Any]],
) -> str:
    if idea_id in completed_ids_any:
        return "built"
    current = state.get(str(idea_id), {})
    status = str(current.get("status", "new")).strip().lower()
    if status in {"deferred", "expired"}:
        return status
    return "new"


def _update_lifecycle_state(
    *,
    state: dict[str, dict[str, Any]],
    all_ideas: list[Idea],
    ideas_for_today: list[Idea],
    top3: list[Idea],
    completed_ids_any: set[int],
    epoch: str,
) -> dict[str, dict[str, Any]]:
    idea_ids_today = {idea.idx for idea in ideas_for_today}
    idea_ids_top3 = {idea.idx for idea in top3}
    for idea in all_ideas:
        key = str(idea.idx)
        entry = dict(state.get(key, {}))
        entry.setdefault("first_seen_epoch", epoch)
        entry["last_seen_epoch"] = epoch
        entry["title"] = idea.title
        entry["category"] = idea.category
        if idea.idx in completed_ids_any:
            entry["status"] = "built"
            entry["built_epoch"] = epoch
            entry["defer_streak"] = 0
            state[key] = entry
            continue

        status = str(entry.get("status", "new")).strip().lower()
        defer_streak = int(entry.get("defer_streak", 0) or 0)
        if idea.idx in idea_ids_top3:
            entry["times_top3"] = int(entry.get("times_top3", 0) or 0) + 1
            entry["defer_streak"] = 0
            if status not in {"expired"}:
                entry["status"] = "new"
        elif idea.idx in idea_ids_today:
            defer_streak += 1
            entry["defer_streak"] = defer_streak
            entry["times_seen_not_top3"] = int(entry.get("times_seen_not_top3", 0) or 0) + 1
            if defer_streak >= 4:
                entry["status"] = "expired"
                entry["expired_reason"] = "te vaak niet gekozen voor top 3"
                entry["expired_epoch"] = epoch
            elif defer_streak >= 2:
                entry["status"] = "deferred"
                entry["deferred_reason"] = "meerdere runs niet gekozen voor top 3"
                entry["deferred_since_epoch"] = epoch
            elif status not in {"deferred", "expired"}:
                entry["status"] = "new"
        state[key] = entry
    return state


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
    epoch: str,
    linter_root: Path | None,
) -> list[ActionItem]:
    epoch_tag = (epoch or "onbekend").strip() or "onbekend"
    selected = [idea for idea in top3 if idea.idx != favorite.idx][:2]
    action_items: list[ActionItem] = []
    for idea in selected:
        action_items.append(
            ActionItem(
                task=f"Implementeer idee {idea.idx}: [{idea.category}] {idea.title}",
                goal=idea.impact,
                command=_command_for_idea(idea=idea, summary_path=summary_path, linter_root=linter_root),
                check=idea.acceptance,
                evidence=f"workspace/codex/night/ochtendtest/{epoch_tag}_idea_{idea.idx}_done.txt",
            )
        )

    action_items.append(
        ActionItem(
            task="Draai gerichte regressietests voor report + linter",
            goal="Bevestigen dat ochtendrapport en link-depth linting stabiel blijven.",
            command="pytest -q tests/test_morning_reporter.py tests/test_skill_linter.py",
            check="Pytest toont alle geselecteerde tests als geslaagd.",
            evidence=f"workspace/codex/night/ochtendtest/{epoch_tag}_pytest_regressie.txt",
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
    skill_index_output: Path | None = None,
    completed_ideas_dir: Path | None = None,
    lifecycle_state_path: Path | None = None,
) -> str:
    epoch = str(summary.get("epoch", "onbekend"))
    tasks_executed = int(summary.get("tasks_executed", 0) or 0)
    tasks_skipped = int(summary.get("tasks_skipped", 0) or 0)
    tasks_failed = int(summary.get("tasks_failed", 0) or 0)
    budget_used = float(summary.get("budget_used", 0) or 0)
    violations = _violations_count(summary)
    health = _health_label(tasks_failed, violations)
    trend_line = _read_recent_trend(summary_path, window=3)

    skill_lint_line = "- Skill-linter: niet uitgevoerd."
    skill_index_line = ""
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
            if skill_index_output is not None:
                written = _write_skill_index_manifest(lint_results=lint_results, output_path=skill_index_output)
                if written is not None:
                    skill_index_line = f"- Skill-index manifest: `{written}`."

    all_ideas = _build_ideas(tasks_executed, tasks_failed, violations)
    completed_dir = completed_ideas_dir or Path("workspace/codex/night/ochtendtest")
    lifecycle_path = lifecycle_state_path or Path("workspace/codex/night/idea_lifecycle.json")
    lifecycle_state = _load_lifecycle_state(lifecycle_path)
    completed_ids_any = _load_completed_idea_ids(completed_dir)
    completed_ids_epoch = _load_completed_idea_ids(completed_dir, epoch if epoch and epoch != "onbekend" else None)

    active_ideas = [
        idea
        for idea in all_ideas
        if _status_for_idea(idea_id=idea.idx, completed_ids_any=completed_ids_any, state=lifecycle_state)
        not in {"built", "expired"}
    ]
    if len(active_ideas) < 10:
        active_ideas.extend([idea for idea in all_ideas if idea not in active_ideas])
    ideas = active_ideas[:10]

    top3_pool = [idea for idea in ideas if idea.idx not in completed_ids_any]
    if len(top3_pool) < 3:
        top3_pool = ideas
    top3 = sorted(top3_pool, key=lambda idea: (idea.score, -idea.idx), reverse=True)[:3]
    favorite = top3[0]
    favorite_built = favorite.idx in completed_ids_any
    lifecycle_state = _update_lifecycle_state(
        state=lifecycle_state,
        all_ideas=all_ideas,
        ideas_for_today=ideas,
        top3=top3,
        completed_ids_any=completed_ids_any,
        epoch=epoch,
    )
    _save_lifecycle_state(lifecycle_path, lifecycle_state)

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
    if trend_line is not None:
        lines.append(f"- 3-daagse trend: `{trend_line}`.")
    lines.append(skill_lint_line)
    if skill_index_line:
        lines.append(skill_index_line)
    if completed_ids_any:
        done_sorted = ",".join(str(i) for i in sorted(completed_ids_any))
        lines.append(f"- Reeds afgeronde idee-ids (alle epochs): `{done_sorted}`.")
    if completed_ids_epoch:
        done_epoch = ",".join(str(i) for i in sorted(completed_ids_epoch))
        lines.append(f"- Reeds afgeronde idee-ids voor epoch `{epoch}`: `{done_epoch}`.")
    deferred_ids = [
        int(key)
        for key, value in lifecycle_state.items()
        if str(value.get("status", "")).strip().lower() == "deferred"
    ]
    expired_ids = [
        int(key)
        for key, value in lifecycle_state.items()
        if str(value.get("status", "")).strip().lower() == "expired"
    ]
    if deferred_ids:
        lines.append(f"- Deferred idee-ids: `{','.join(str(i) for i in sorted(deferred_ids))}`.")
    if expired_ids:
        lines.append(f"- Expired idee-ids: `{','.join(str(i) for i in sorted(expired_ids))}`.")
    lines.append(f"- Idea lifecycle state: `{lifecycle_path}`.")
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
    for pos, idea in enumerate(ideas, start=1):
        lines.append(f"{pos}. **[{idea.category}] {idea.title}**")
        lines.append(f"Waarom: {idea.why}")
        lines.append(f"Impact: {idea.impact}")
        lines.append(f"Acceptatiecheck: {idea.acceptance}")
        lines.append(f"Score: `{idea.score}`")
        if idea.idx in completed_ids_any:
            lines.append("Status: al eerder afgerond (niet opnieuw voorgesteld voor top 3).")
    lines.append("")

    lines.append("**Mijn Favoriet Om Nu Te Bouwen**")
    lines.append(f"- Gekozen idee: **{favorite.idx}. [{favorite.category}] {favorite.title}**")
    lines.append("- Selectieregel: gekozen uit de top 3 op basis van hoogste score.")
    lines.append(
        "- Waarom nu beste keuze: "
        f"hoge score ({favorite.score}) op directe waarde en lage integratierisico's."
    )
    if favorite_built:
        lines.append("- Buildstatus: uitgevoerd in workspace (lokaal, niet naar remote gepusht).")
    else:
        lines.append("- Buildstatus: gepland voor eerstvolgende uitvoerronde in workspace.")
    lines.append(f"- Eerste concrete implementatiestap in deze workspace: {favorite.first_step}")
    lines.append("")

    lines.append("**Top 3 Voorstel (op score)**")
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
    parser.add_argument("--skill-index-output", default="workspace/codex/night/skill_index.json")
    parser.add_argument("--completed-ideas-dir", default="workspace/codex/night/ochtendtest")
    parser.add_argument("--lifecycle-state-path", default="workspace/codex/night/idea_lifecycle.json")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary_path = Path(args.summary_path)
    summary = _load_summary(summary_path)
    linter_root = Path(args.linter_root).expanduser() if args.linter_root.strip() else None
    skill_index_output = Path(args.skill_index_output).expanduser() if args.skill_index_output.strip() else None
    completed_ideas_dir = Path(args.completed_ideas_dir).expanduser() if args.completed_ideas_dir.strip() else None
    lifecycle_state_path = Path(args.lifecycle_state_path).expanduser() if args.lifecycle_state_path.strip() else None
    report = generate_report(
        summary=summary,
        summary_path=summary_path,
        night_status=str(args.night_status),
        linter_root=linter_root,
        linter_link_depth=max(1, int(args.linter_link_depth or 2)),
        linter_strict_links=bool(args.linter_strict_links),
        skill_index_output=skill_index_output,
        completed_ideas_dir=completed_ideas_dir,
        lifecycle_state_path=lifecycle_state_path,
    )
    if args.output.strip():
        out = Path(args.output)
        out.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

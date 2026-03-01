from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomy_budget.engine import BudgetEngine
from autonomy_budget.engine import BudgetError
from autonomy_budget.engine import DENY_LEDGER_APPEND_FAILED
from autonomy_budget.engine import DENY_LEDGER_CHAIN_INVALID
from autonomy_budget.engine import DENY_POLICY_MISSING
from autonomy_budget.engine import DENY_SKILL_QUOTA_EXCEEDED
from autonomy_budget.engine import DENY_STATE_INVALID


def _resolve_policy_path() -> Path:
    candidates = [
        Path("/home/infra/AI-OS/governance_policy.yaml"),
        Path(__file__).resolve().parents[1] / "governance_policy.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    pytest.skip(
        "Phase-K policy file not available in this environment; expected governance_policy.yaml",
        allow_module_level=False,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n", encoding="utf-8")


def _base_state() -> dict:
    return {
        "agents": {
            "agent-a": {
                "meta": {
                    "trust_level": "MEDIUM",
                    "forced_escalations": 0,
                    "consecutive_clean_epochs": 0,
                    "escalation_token": False,
                },
                "epochs": {},
            },
            "agent-b": {
                "meta": {
                    "trust_level": "MEDIUM",
                    "forced_escalations": 0,
                    "consecutive_clean_epochs": 0,
                    "escalation_token": False,
                },
                "epochs": {},
            },
        },
        "epoch_order": ["2026-02-25", "2026-02-26", "2026-02-27", "2026-02-28"],
        "ledger_chain_status": {"last_verified_epoch": None, "last_hash": ""},
    }


def _engine(tmp_path: Path) -> BudgetEngine:
    policy = _resolve_policy_path()
    state_path = tmp_path / "state.json"
    _write_json(state_path, _base_state())
    return BudgetEngine(policy, state_path, tmp_path / "audit" / "budget_ledger")


def test_trust_upgrade_after_clean_epochs(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    r1 = engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-25", event_id="e1", ts_utc="2026-02-25T00:00:00Z")
    r2 = engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-26", event_id="e2", ts_utc="2026-02-26T00:00:00Z")
    r3 = engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-27", event_id="e3", ts_utc="2026-02-27T00:00:00Z")

    assert r1.ok and r2.ok and r3.ok
    assert r3.data["old_trust_level"] == "MEDIUM"
    assert r3.data["new_trust_level"] == "HIGH"


def test_trust_downgrade_on_violation(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    # First escalate once to HIGH.
    engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-25", event_id="e1", ts_utc="2026-02-25T00:00:00Z")
    engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-26", event_id="e2", ts_utc="2026-02-26T00:00:00Z")
    engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-27", event_id="e3", ts_utc="2026-02-27T00:00:00Z")

    down = engine.update_trust_level(
        "agent-a",
        [{"type": "budget_violation"}],
        epoch_id="2026-02-28",
        event_id="e4",
        ts_utc="2026-02-28T00:00:00Z",
    )
    assert down.ok
    assert down.data["old_trust_level"] == "HIGH"
    assert down.data["new_trust_level"] == "MEDIUM"


def test_risk_multiplier_affects_effective_budget_and_quota(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    state = engine.load_state()

    low = engine.calculate_effective_budget(
        {"tokens": 100, "external_calls": 10},
        "MEDIUM",
        "LOW",
        agent_id="agent-a",
        current_epoch="2026-02-25",
        state=state,
    )
    high = engine.calculate_effective_budget(
        {"tokens": 100, "external_calls": 10},
        "MEDIUM",
        "HIGH",
        agent_id="agent-a",
        current_epoch="2026-02-25",
        state=state,
    )

    assert low["tokens"] > high["tokens"]
    assert low["external_calls"] > high["external_calls"]

    quota_low = engine.calculate_effective_quota(50, "MEDIUM", "LOW", agent_id="agent-a", current_epoch="2026-02-25", state=state)
    quota_high = engine.calculate_effective_quota(50, "MEDIUM", "HIGH", agent_id="agent-a", current_epoch="2026-02-25", state=state)
    assert quota_low > quota_high


def test_skill_quota_enforcement_denies_when_exceeded(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    # MEDIUM trust + HIGH risk on email(10) => floor(10*1.0/2.0)=5
    for i in range(5):
        verdict = engine.enforce_skill_quota(
            "agent-a",
            "email",
            "HIGH",
            epoch_id="2026-02-25",
            event_id=f"c{i}",
            ts_utc="2026-02-25T00:00:00Z",
        )
        assert verdict.ok

    denied = engine.enforce_skill_quota(
        "agent-a",
        "email",
        "HIGH",
        epoch_id="2026-02-25",
        event_id="deny-1",
        ts_utc="2026-02-25T00:01:00Z",
    )
    assert not denied.ok
    assert denied.reason_code == DENY_SKILL_QUOTA_EXCEEDED


def test_hash_chain_tamper_detection(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.enforce_skill_quota("agent-a", "telegram", "LOW", epoch_id="2026-02-25", event_id="t1", ts_utc="2026-02-25T00:00:00Z")
    engine.enforce_skill_quota("agent-a", "telegram", "LOW", epoch_id="2026-02-25", event_id="t2", ts_utc="2026-02-25T00:01:00Z")

    ledger = tmp_path / "audit" / "budget_ledger" / "2026-02-25.jsonl"
    lines = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tampered = json.loads(lines[0])
    tampered["action"] = "tampered_action"
    lines[0] = json.dumps(tampered, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verdict = engine.verify_chain("2026-02-25")
    assert not verdict.ok
    assert verdict.reason_code == DENY_LEDGER_CHAIN_INVALID


def test_replay_determinism_identical_results(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.enforce_skill_quota("agent-a", "git_commit", "MEDIUM", epoch_id="2026-02-25", event_id="r1", ts_utc="2026-02-25T00:00:00Z")
    engine.update_trust_level("agent-a", [{"type": "clean"}], epoch_id="2026-02-25", event_id="r2", ts_utc="2026-02-25T01:00:00Z")

    first = engine.replay_ledger("2026-02-25")
    second = engine.replay_ledger("2026-02-25")

    assert first.ok and second.ok
    assert first.data == second.data


def test_cross_agent_propagation_reduces_quota(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    state = engine.load_state()
    state["agents"]["agent-a"]["epochs"]["2026-02-25"] = {
        "skill_used": {},
        "violations": 1,
        "high_risk_overflow": 1,
        "hash_inconsistency": False,
    }
    engine.save_state_atomic(state)
    fresh = engine.load_state()

    no_prop = engine.calculate_effective_quota(20, "MEDIUM", "LOW", agent_id="agent-a", current_epoch="2026-02-25", state=fresh)
    with_prop = engine.calculate_effective_quota(20, "MEDIUM", "LOW", agent_id="agent-b", current_epoch="2026-02-25", state=fresh)

    assert with_prop < no_prop


def test_fail_closed_missing_policy(tmp_path: Path) -> None:
    with pytest.raises(BudgetError) as exc:
        BudgetEngine(tmp_path / "missing.yaml", tmp_path / "state.json", tmp_path / "audit")
    assert exc.value.reason_code == DENY_POLICY_MISSING


def test_fail_closed_invalid_state(tmp_path: Path) -> None:
    policy = _resolve_policy_path()
    bad_state = tmp_path / "state.json"
    _write_json(bad_state, {"agents": {}})
    engine = BudgetEngine(policy, bad_state, tmp_path / "audit" / "budget_ledger")
    with pytest.raises(BudgetError) as exc:
        engine.load_state()
    assert exc.value.reason_code == DENY_STATE_INVALID


def test_fail_closed_when_ledger_append_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(tmp_path)

    def _boom(path: Path, line: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(engine, "_append_jsonl_line", _boom)
    with pytest.raises(BudgetError) as exc:
        engine.enforce_skill_quota(
            "agent-a",
            "telegram",
            "LOW",
            epoch_id="2026-02-25",
            event_id="err1",
            ts_utc="2026-02-25T00:00:00Z",
        )

    assert exc.value.reason_code == DENY_LEDGER_APPEND_FAILED

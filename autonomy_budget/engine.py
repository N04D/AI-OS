from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any

import yaml

DENY_POLICY_MISSING = "DENY_POLICY_MISSING"
DENY_POLICY_INVALID = "DENY_POLICY_INVALID"
DENY_LEDGER_APPEND_FAILED = "DENY_LEDGER_APPEND_FAILED"
DENY_LEDGER_CHAIN_INVALID = "DENY_LEDGER_CHAIN_INVALID"
DENY_BUDGET_EXCEEDED = "DENY_BUDGET_EXCEEDED"
DENY_SKILL_QUOTA_EXCEEDED = "DENY_SKILL_QUOTA_EXCEEDED"
DENY_ESCALATION_REQUIRED = "DENY_ESCALATION_REQUIRED"
DENY_STATE_INVALID = "DENY_STATE_INVALID"

_REQUIRED_POLICY_KEYS = {
    "schema_version",
    "timezone",
    "epoch",
    "hashing",
    "validation",
    "trust_levels",
    "risk_profiles",
    "skill_quotas",
    "trust_evolution",
    "cross_agent_risk",
    "ledger",
}

_REQUIRED_STATE_KEYS = {
    "agents",
    "epoch_order",
    "ledger_chain_status",
}


class BudgetError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason_code: str | None
    data: dict[str, Any]


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    ts_utc: str
    agent_id: str
    epoch: str
    action: str
    risk_profile: str
    trust_level: str
    budget_before: dict[str, Any]
    budget_delta: dict[str, Any]
    budget_after: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts_utc": self.ts_utc,
            "agent_id": self.agent_id,
            "epoch": self.epoch,
            "action": self.action,
            "risk_profile": self.risk_profile,
            "trust_level": self.trust_level,
            "budget_before": self.budget_before,
            "budget_delta": self.budget_delta,
            "budget_after": self.budget_after,
        }


def canonical_json(obj: dict[str, Any]) -> str:
    """Return canonical JSON exactly as policy requires.

    Deterministic settings are fixed to:
    sort_keys=True, separators=(',', ':'), ensure_ascii=True.
    """
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except Exception as exc:
        raise BudgetError(DENY_STATE_INVALID, f"canonical_json_failed:{exc}") from exc


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _validate_multiplier(value: Any, key: str) -> None:
    try:
        dec = _as_decimal(value)
    except Exception as exc:
        raise BudgetError(DENY_POLICY_INVALID, f"invalid_decimal:{key}") from exc
    if dec <= Decimal("0"):
        raise BudgetError(DENY_POLICY_INVALID, f"non_positive_multiplier:{key}")


def _validate_state_shape(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise BudgetError(DENY_STATE_INVALID, "state_not_object")
    if set(state.keys()) != _REQUIRED_STATE_KEYS:
        raise BudgetError(DENY_STATE_INVALID, "state_keys_invalid")
    agents = state.get("agents")
    epoch_order = state.get("epoch_order")
    chain = state.get("ledger_chain_status")
    if not isinstance(agents, dict):
        raise BudgetError(DENY_STATE_INVALID, "agents_not_object")
    if not isinstance(epoch_order, list) or not all(isinstance(x, str) and x for x in epoch_order):
        raise BudgetError(DENY_STATE_INVALID, "epoch_order_invalid")
    if not isinstance(chain, dict):
        raise BudgetError(DENY_STATE_INVALID, "ledger_chain_status_invalid")

    for agent_id, agent in agents.items():
        if not isinstance(agent_id, str) or not agent_id:
            raise BudgetError(DENY_STATE_INVALID, "agent_id_invalid")
        if not isinstance(agent, dict):
            raise BudgetError(DENY_STATE_INVALID, f"agent_not_object:{agent_id}")
        required_agent_keys = {"meta", "epochs"}
        if set(agent.keys()) != required_agent_keys:
            raise BudgetError(DENY_STATE_INVALID, f"agent_keys_invalid:{agent_id}")
        meta = agent["meta"]
        epochs = agent["epochs"]
        if set(meta.keys()) != {"trust_level", "forced_escalations", "consecutive_clean_epochs", "escalation_token"}:
            raise BudgetError(DENY_STATE_INVALID, f"agent_meta_keys_invalid:{agent_id}")
        if not isinstance(epochs, dict):
            raise BudgetError(DENY_STATE_INVALID, f"agent_epochs_invalid:{agent_id}")
        for epoch_id, ep in epochs.items():
            if not isinstance(epoch_id, str) or not epoch_id:
                raise BudgetError(DENY_STATE_INVALID, f"epoch_id_invalid:{agent_id}")
            if not isinstance(ep, dict):
                raise BudgetError(DENY_STATE_INVALID, f"epoch_entry_invalid:{agent_id}:{epoch_id}")
            expected_ep_keys = {"skill_used", "violations", "high_risk_overflow", "hash_inconsistency"}
            if set(ep.keys()) != expected_ep_keys:
                raise BudgetError(DENY_STATE_INVALID, f"epoch_keys_invalid:{agent_id}:{epoch_id}")
            if not isinstance(ep["skill_used"], dict):
                raise BudgetError(DENY_STATE_INVALID, f"skill_used_invalid:{agent_id}:{epoch_id}")
            if not isinstance(ep["violations"], int) or ep["violations"] < 0:
                raise BudgetError(DENY_STATE_INVALID, f"violations_invalid:{agent_id}:{epoch_id}")
            if not isinstance(ep["high_risk_overflow"], int) or ep["high_risk_overflow"] < 0:
                raise BudgetError(DENY_STATE_INVALID, f"overflow_invalid:{agent_id}:{epoch_id}")
            if not isinstance(ep["hash_inconsistency"], bool):
                raise BudgetError(DENY_STATE_INVALID, f"hash_inconsistency_invalid:{agent_id}:{epoch_id}")
    return state


class BudgetEngine:
    def __init__(self, policy_path: Path, state_path: Path, ledger_root: Path | None = None) -> None:
        self.policy_path = policy_path
        self.state_path = state_path
        self.policy = self.load_policy(policy_path)
        if ledger_root is None:
            ledger_root = Path(str(self.policy["ledger"]["base_dir"]))
        self.ledger_root = ledger_root

    @staticmethod
    def load_policy(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise BudgetError(DENY_POLICY_MISSING, f"missing_policy:{path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise BudgetError(DENY_POLICY_INVALID, "policy_not_object")
        if set(payload.keys()) != _REQUIRED_POLICY_KEYS:
            raise BudgetError(DENY_POLICY_INVALID, "policy_keys_invalid")
        if payload.get("schema_version") != "autonomy-budget.v1":
            raise BudgetError(DENY_POLICY_INVALID, "schema_version_invalid")
        if payload.get("timezone") != "UTC":
            raise BudgetError(DENY_POLICY_INVALID, "timezone_invalid")
        epoch = payload.get("epoch")
        if not isinstance(epoch, dict) or epoch.get("type") != "daily_utc":
            raise BudgetError(DENY_POLICY_INVALID, "epoch_invalid")

        hashing = payload.get("hashing")
        if not isinstance(hashing, dict):
            raise BudgetError(DENY_POLICY_INVALID, "hashing_invalid")
        if hashing.get("algorithm") != "sha256":
            raise BudgetError(DENY_POLICY_INVALID, "hash_algorithm_invalid")
        expected_canonical = "sorted_keys,separators=(',',':'),ensure_ascii=true"
        if hashing.get("canonical_json") != expected_canonical:
            raise BudgetError(DENY_POLICY_INVALID, "canonical_json_settings_invalid")

        validation = payload.get("validation")
        if not isinstance(validation, dict):
            raise BudgetError(DENY_POLICY_INVALID, "validation_invalid")
        if validation.get("require_all_keys") is not True or validation.get("forbid_unknown_keys") is not True:
            raise BudgetError(DENY_POLICY_INVALID, "strict_validation_required")

        trust_levels = payload.get("trust_levels")
        risk_profiles = payload.get("risk_profiles")
        skill_quotas = payload.get("skill_quotas")
        cross_agent_risk = payload.get("cross_agent_risk")
        trust_evolution = payload.get("trust_evolution")
        ledger = payload.get("ledger")

        if not isinstance(trust_levels, dict) or sorted(trust_levels.keys()) != ["HIGH", "LOW", "MEDIUM"]:
            raise BudgetError(DENY_POLICY_INVALID, "trust_levels_invalid")
        if not isinstance(risk_profiles, dict) or sorted(risk_profiles.keys()) != ["HIGH", "LOW", "MEDIUM"]:
            raise BudgetError(DENY_POLICY_INVALID, "risk_profiles_invalid")
        if not isinstance(skill_quotas, dict) or not skill_quotas:
            raise BudgetError(DENY_POLICY_INVALID, "skill_quotas_invalid")
        if not isinstance(cross_agent_risk, dict):
            raise BudgetError(DENY_POLICY_INVALID, "cross_agent_risk_invalid")
        if not isinstance(trust_evolution, dict):
            raise BudgetError(DENY_POLICY_INVALID, "trust_evolution_invalid")
        if not isinstance(ledger, dict):
            raise BudgetError(DENY_POLICY_INVALID, "ledger_invalid")

        for level_name, cfg in trust_levels.items():
            if not isinstance(cfg, dict) or set(cfg.keys()) != {"token_multiplier", "external_io_multiplier", "max_escalations"}:
                raise BudgetError(DENY_POLICY_INVALID, f"trust_level_invalid:{level_name}")
            _validate_multiplier(cfg.get("token_multiplier"), f"trust.token_multiplier.{level_name}")
            _validate_multiplier(cfg.get("external_io_multiplier"), f"trust.external_io_multiplier.{level_name}")
            if not isinstance(cfg.get("max_escalations"), int) or int(cfg["max_escalations"]) < 0:
                raise BudgetError(DENY_POLICY_INVALID, f"max_escalations_invalid:{level_name}")

        for risk_name, cfg in risk_profiles.items():
            if not isinstance(cfg, dict) or set(cfg.keys()) != {"token_cost_multiplier", "external_call_cost_multiplier"}:
                raise BudgetError(DENY_POLICY_INVALID, f"risk_profile_invalid:{risk_name}")
            _validate_multiplier(cfg.get("token_cost_multiplier"), f"risk.token_cost_multiplier.{risk_name}")
            _validate_multiplier(cfg.get("external_call_cost_multiplier"), f"risk.external_call_cost_multiplier.{risk_name}")

        for skill, cfg in skill_quotas.items():
            if not isinstance(skill, str) or not skill:
                raise BudgetError(DENY_POLICY_INVALID, "skill_name_invalid")
            if not isinstance(cfg, dict) or set(cfg.keys()) != {"base_limit", "requires_escalation"}:
                raise BudgetError(DENY_POLICY_INVALID, f"skill_quota_invalid:{skill}")
            if not isinstance(cfg["base_limit"], int) or cfg["base_limit"] < 0:
                raise BudgetError(DENY_POLICY_INVALID, f"skill_base_limit_invalid:{skill}")
            if not isinstance(cfg["requires_escalation"], bool):
                raise BudgetError(DENY_POLICY_INVALID, f"skill_requires_escalation_invalid:{skill}")

        if set(cross_agent_risk.keys()) != {"enabled", "propagation_factor", "shared_risk_window_epochs"}:
            raise BudgetError(DENY_POLICY_INVALID, "cross_agent_risk_keys_invalid")
        if not isinstance(cross_agent_risk["enabled"], bool):
            raise BudgetError(DENY_POLICY_INVALID, "cross_agent_enabled_invalid")
        _validate_multiplier(Decimal("1") - Decimal(str(1 - float(cross_agent_risk["propagation_factor"]))), "cross_agent.propagation_factor")
        pf = float(cross_agent_risk["propagation_factor"])
        if pf < 0.0 or pf > 1.0:
            raise BudgetError(DENY_POLICY_INVALID, "cross_agent_propagation_factor_out_of_range")
        if not isinstance(cross_agent_risk["shared_risk_window_epochs"], int) or cross_agent_risk["shared_risk_window_epochs"] < 1:
            raise BudgetError(DENY_POLICY_INVALID, "shared_risk_window_epochs_invalid")

        if set(ledger.keys()) != {"base_dir", "file_name_pattern", "append_only", "fail_closed_on_write_error"}:
            raise BudgetError(DENY_POLICY_INVALID, "ledger_keys_invalid")
        if ledger.get("append_only") is not True:
            raise BudgetError(DENY_POLICY_INVALID, "ledger_append_only_required")
        if ledger.get("fail_closed_on_write_error") is not True:
            raise BudgetError(DENY_POLICY_INVALID, "ledger_fail_closed_required")

        return payload

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise BudgetError(DENY_STATE_INVALID, f"missing_state:{self.state_path}")
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BudgetError(DENY_STATE_INVALID, f"invalid_state_json:{exc}") from exc
        return _validate_state_shape(payload)

    def save_state_atomic(self, state: dict[str, Any]) -> None:
        normalized = _validate_state_shape(state)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        text = canonical_json(normalized) + "\n"
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.state_path)

    def _ledger_path(self, epoch_id: str) -> Path:
        return self.ledger_root / f"{epoch_id}.jsonl"

    def _read_last_hash(self, path: Path) -> str:
        if not path.exists():
            return ""
        last_non_empty = ""
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last_non_empty = line.strip()
        if not last_non_empty:
            return ""
        obj = json.loads(last_non_empty)
        return str(obj.get("hash", ""))

    def _append_jsonl_line(self, path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    def append_event(self, event: LedgerEvent) -> dict[str, Any]:
        path = self._ledger_path(event.epoch)
        path.parent.mkdir(parents=True, exist_ok=True)

        body = event.as_dict()
        prev_hash = self._read_last_hash(path)
        body["hash_prev"] = prev_hash
        payload_no_hash = canonical_json(body)
        body["hash"] = _sha256_hex(payload_no_hash)
        line = canonical_json(body) + "\n"

        try:
            self._append_jsonl_line(path, line)
        except Exception as exc:
            raise BudgetError(DENY_LEDGER_APPEND_FAILED, f"append_failed:{exc}") from exc

        return body

    def verify_chain(self, epoch_id: str) -> Verdict:
        path = self._ledger_path(epoch_id)
        if not path.exists():
            return Verdict(ok=True, reason_code=None, data={"events": 0, "last_hash": ""})

        prev_hash = ""
        events = 0
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, start=1):
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if str(obj.get("hash_prev", "")) != prev_hash:
                        return Verdict(False, DENY_LEDGER_CHAIN_INVALID, {"line": line_no, "reason": "hash_prev_mismatch"})
                    got_hash = str(obj.get("hash", ""))
                    if not got_hash:
                        return Verdict(False, DENY_LEDGER_CHAIN_INVALID, {"line": line_no, "reason": "hash_missing"})
                    body = dict(obj)
                    body.pop("hash", None)
                    expect = _sha256_hex(canonical_json(body))
                    if got_hash != expect:
                        return Verdict(False, DENY_LEDGER_CHAIN_INVALID, {"line": line_no, "reason": "hash_mismatch"})
                    prev_hash = got_hash
                    events += 1
        except Exception as exc:
            return Verdict(False, DENY_LEDGER_CHAIN_INVALID, {"reason": f"ledger_read_failed:{exc}"})

        return Verdict(ok=True, reason_code=None, data={"events": events, "last_hash": prev_hash})

    def replay_ledger(self, epoch_id: str) -> Verdict:
        verify = self.verify_chain(epoch_id)
        if not verify.ok:
            return verify
        path = self._ledger_path(epoch_id)
        replay = {
            "quota_consumes": 0,
            "quota_denies": 0,
            "trust_transitions": 0,
            "last_hash": verify.data.get("last_hash", ""),
        }
        if not path.exists():
            return Verdict(True, None, replay)

        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                obj = json.loads(line)
                action = str(obj.get("action", ""))
                if action == "quota_consume":
                    replay["quota_consumes"] += 1
                elif action == "quota_deny":
                    replay["quota_denies"] += 1
                elif action == "trust_transition":
                    replay["trust_transitions"] += 1
        return Verdict(True, None, replay)

    def _trust_multipliers(self, trust_level: str) -> tuple[Decimal, Decimal]:
        cfg = self.policy["trust_levels"].get(trust_level)
        if not isinstance(cfg, dict):
            raise BudgetError(DENY_POLICY_INVALID, f"unknown_trust_level:{trust_level}")
        return _as_decimal(cfg["token_multiplier"]), _as_decimal(cfg["external_io_multiplier"])

    def _risk_multipliers(self, risk_profile: str) -> tuple[Decimal, Decimal]:
        cfg = self.policy["risk_profiles"].get(risk_profile)
        if not isinstance(cfg, dict):
            raise BudgetError(DENY_POLICY_INVALID, f"unknown_risk_profile:{risk_profile}")
        return _as_decimal(cfg["token_cost_multiplier"]), _as_decimal(cfg["external_call_cost_multiplier"])

    def calculate_shared_risk_adjustment(self, agent_id: str, current_epoch: str, state: dict[str, Any]) -> Decimal:
        cfg = self.policy["cross_agent_risk"]
        if not bool(cfg["enabled"]):
            return Decimal("1")

        if current_epoch not in state["epoch_order"]:
            raise BudgetError(DENY_STATE_INVALID, f"epoch_not_in_state:{current_epoch}")

        idx = state["epoch_order"].index(current_epoch)
        window = int(cfg["shared_risk_window_epochs"])
        start = max(0, idx - window + 1)
        relevant_epochs = set(state["epoch_order"][start : idx + 1])

        overflow_seen = False
        for other_agent_id, agent in state["agents"].items():
            if other_agent_id == agent_id:
                continue
            epochs = agent["epochs"]
            for epoch in relevant_epochs:
                ep = epochs.get(epoch)
                if not isinstance(ep, dict):
                    continue
                if int(ep.get("high_risk_overflow", 0)) > 0:
                    overflow_seen = True
                    break
            if overflow_seen:
                break

        if not overflow_seen:
            return Decimal("1")
        factor = _as_decimal(cfg["propagation_factor"])
        return Decimal("1") - factor

    def calculate_effective_budget(
        self,
        base: dict[str, int],
        trust_level: str,
        risk_profile: str,
        *,
        agent_id: str,
        current_epoch: str,
        state: dict[str, Any],
    ) -> dict[str, int]:
        """Compute deterministic effective token/external budgets.

        base is required as {"tokens": int, "external_calls": int}.
        """
        if set(base.keys()) != {"tokens", "external_calls"}:
            raise BudgetError(DENY_STATE_INVALID, "base_budget_shape_invalid")
        if not isinstance(base["tokens"], int) or base["tokens"] < 0:
            raise BudgetError(DENY_STATE_INVALID, "base_tokens_invalid")
        if not isinstance(base["external_calls"], int) or base["external_calls"] < 0:
            raise BudgetError(DENY_STATE_INVALID, "base_external_calls_invalid")

        token_tm, ext_tm = self._trust_multipliers(trust_level)
        token_rm, ext_rm = self._risk_multipliers(risk_profile)
        shared_adj = self.calculate_shared_risk_adjustment(agent_id, current_epoch, state)
        token_tm *= shared_adj
        ext_tm *= shared_adj

        if token_tm <= 0 or ext_tm <= 0:
            raise BudgetError(DENY_STATE_INVALID, "effective_trust_multiplier_non_positive")

        tokens = int((Decimal(base["tokens"]) * token_tm / token_rm).to_integral_value(rounding=ROUND_FLOOR))
        external_calls = int((Decimal(base["external_calls"]) * ext_tm / ext_rm).to_integral_value(rounding=ROUND_FLOOR))
        return {"tokens": max(0, tokens), "external_calls": max(0, external_calls)}

    def calculate_effective_quota(
        self,
        base_limit: int,
        trust_level: str,
        risk_profile: str,
        *,
        agent_id: str,
        current_epoch: str,
        state: dict[str, Any],
    ) -> int:
        """Compute deterministic invocation quota limit.

        effective_limit = floor(base_limit * trust_token_multiplier / risk_token_multiplier)
        then multiplied by one cross-agent adjustment factor.
        """
        if not isinstance(base_limit, int) or base_limit < 0:
            raise BudgetError(DENY_STATE_INVALID, "base_limit_invalid")

        token_tm, _ = self._trust_multipliers(trust_level)
        token_rm, _ = self._risk_multipliers(risk_profile)
        shared_adj = self.calculate_shared_risk_adjustment(agent_id, current_epoch, state)

        effective = Decimal(base_limit) * token_tm * shared_adj / token_rm
        out = int(effective.to_integral_value(rounding=ROUND_FLOOR))
        return max(0, out)

    def _effective_cost(
        self,
        tokens_used: int,
        external_calls_used: int,
        trust_level: str,
        risk_profile: str,
        *,
        agent_id: str,
        current_epoch: str,
        state: dict[str, Any],
    ) -> dict[str, int]:
        if not isinstance(tokens_used, int) or tokens_used < 0:
            raise BudgetError(DENY_STATE_INVALID, "tokens_used_invalid")
        if not isinstance(external_calls_used, int) or external_calls_used < 0:
            raise BudgetError(DENY_STATE_INVALID, "external_calls_used_invalid")

        token_tm, ext_tm = self._trust_multipliers(trust_level)
        token_rm, ext_rm = self._risk_multipliers(risk_profile)
        shared_adj = self.calculate_shared_risk_adjustment(agent_id, current_epoch, state)
        token_tm *= shared_adj
        ext_tm *= shared_adj

        if token_tm <= 0 or ext_tm <= 0:
            raise BudgetError(DENY_STATE_INVALID, "effective_trust_multiplier_non_positive")

        token_cost = int((Decimal(tokens_used) * token_rm / token_tm).to_integral_value(rounding=ROUND_CEILING))
        external_cost = int((Decimal(external_calls_used) * ext_rm / ext_tm).to_integral_value(rounding=ROUND_CEILING))
        return {"tokens": token_cost, "external_calls": external_cost}

    def _ensure_epoch(self, state: dict[str, Any], epoch_id: str) -> None:
        if epoch_id not in state["epoch_order"]:
            state["epoch_order"].append(epoch_id)

    def _agent_epoch_entry(self, state: dict[str, Any], agent_id: str, epoch_id: str) -> dict[str, Any]:
        agents = state["agents"]
        if agent_id not in agents:
            raise BudgetError(DENY_STATE_INVALID, f"unknown_agent:{agent_id}")
        agent = agents[agent_id]
        epochs = agent["epochs"]
        if epoch_id not in epochs:
            epochs[epoch_id] = {
                "skill_used": {},
                "violations": 0,
                "high_risk_overflow": 0,
                "hash_inconsistency": False,
            }
        return epochs[epoch_id]

    def enforce_skill_quota(
        self,
        agent_id: str,
        skill: str,
        risk_profile: str,
        *,
        epoch_id: str,
        event_id: str,
        ts_utc: str,
        tokens_used: int = 0,
        external_calls_used: int = 0,
    ) -> Verdict:
        state = self.load_state()
        self._ensure_epoch(state, epoch_id)

        if skill not in self.policy["skill_quotas"]:
            raise BudgetError(DENY_POLICY_INVALID, f"unknown_skill:{skill}")
        if risk_profile not in self.policy["risk_profiles"]:
            raise BudgetError(DENY_POLICY_INVALID, f"unknown_risk_profile:{risk_profile}")

        agent_meta = state["agents"][agent_id]["meta"]
        trust_level = str(agent_meta["trust_level"])
        quota_cfg = self.policy["skill_quotas"][skill]
        if quota_cfg["requires_escalation"] and not bool(agent_meta["escalation_token"]):
            return Verdict(False, DENY_ESCALATION_REQUIRED, {"agent_id": agent_id, "skill": skill})

        epoch_entry = self._agent_epoch_entry(state, agent_id, epoch_id)
        used_before = int(epoch_entry["skill_used"].get(skill, 0))
        base_limit = int(quota_cfg["base_limit"])
        effective_limit = self.calculate_effective_quota(
            base_limit,
            trust_level,
            risk_profile,
            agent_id=agent_id,
            current_epoch=epoch_id,
            state=state,
        )
        effective_cost = self._effective_cost(
            tokens_used=tokens_used,
            external_calls_used=external_calls_used,
            trust_level=trust_level,
            risk_profile=risk_profile,
            agent_id=agent_id,
            current_epoch=epoch_id,
            state=state,
        )

        if used_before + 1 > effective_limit:
            epoch_entry["violations"] += 1
            if risk_profile == "HIGH":
                epoch_entry["high_risk_overflow"] += 1
            event = LedgerEvent(
                event_id=event_id,
                ts_utc=ts_utc,
                agent_id=agent_id,
                epoch=epoch_id,
                action="quota_deny",
                risk_profile=risk_profile,
                trust_level=trust_level,
                budget_before={"used": used_before, "effective_limit": effective_limit},
                budget_delta={"used": 0, "effective_cost": effective_cost},
                budget_after={"used": used_before, "effective_limit": effective_limit},
            )
            self.append_event(event)
            self.save_state_atomic(state)
            return Verdict(False, DENY_SKILL_QUOTA_EXCEEDED, {
                "agent_id": agent_id,
                "skill": skill,
                "used": used_before,
                "effective_limit": effective_limit,
            })

        epoch_entry["skill_used"][skill] = used_before + 1
        event = LedgerEvent(
            event_id=event_id,
            ts_utc=ts_utc,
            agent_id=agent_id,
            epoch=epoch_id,
            action="quota_consume",
            risk_profile=risk_profile,
            trust_level=trust_level,
            budget_before={"used": used_before, "effective_limit": effective_limit},
            budget_delta={"used": 1, "effective_cost": effective_cost},
            budget_after={"used": used_before + 1, "effective_limit": effective_limit},
        )
        self.append_event(event)
        self.save_state_atomic(state)
        return Verdict(True, None, {
            "agent_id": agent_id,
            "skill": skill,
            "used": used_before + 1,
            "effective_limit": effective_limit,
        })

    def update_trust_level(
        self,
        agent_id: str,
        epoch_events: list[dict[str, Any]],
        *,
        epoch_id: str,
        event_id: str,
        ts_utc: str,
    ) -> Verdict:
        state = self.load_state()
        self._ensure_epoch(state, epoch_id)

        if agent_id not in state["agents"]:
            raise BudgetError(DENY_STATE_INVALID, f"unknown_agent:{agent_id}")
        agent = state["agents"][agent_id]
        meta = agent["meta"]
        current_level = str(meta["trust_level"])
        levels = ["LOW", "MEDIUM", "HIGH"]
        current_idx = levels.index(current_level)

        rules = self.policy["trust_evolution"]
        max_escalations = int(self.policy["trust_levels"][current_level]["max_escalations"])

        has_budget_violation = any(str(ev.get("type", "")) == "budget_violation" for ev in epoch_events)
        has_hash_issue = any(str(ev.get("type", "")) == "hash_inconsistency" for ev in epoch_events)
        has_forced_escalation = any(str(ev.get("type", "")) == "forced_escalation" for ev in epoch_events)
        high_risk_overflow = sum(1 for ev in epoch_events if str(ev.get("type", "")) == "high_risk_overflow")

        should_downgrade = (
            (rules["downgrade_on_budget_violation"] and has_budget_violation)
            or (rules["downgrade_on_hash_inconsistency"] and has_hash_issue)
            or (rules["downgrade_on_escalation_limit_exceeded"] and int(meta["forced_escalations"]) > max_escalations)
            or (rules["downgrade_on_high_risk_overflow"] and high_risk_overflow >= int(rules["high_risk_overflow_threshold"]))
            or has_forced_escalation
        )

        if should_downgrade:
            new_idx = max(0, current_idx - 1)
            meta["consecutive_clean_epochs"] = 0
        else:
            clean = int(meta["consecutive_clean_epochs"]) + 1
            needed = int(rules["clean_epochs_for_upgrade"])
            if clean >= needed:
                new_idx = min(len(levels) - 1, current_idx + 1)
                meta["consecutive_clean_epochs"] = 0
            else:
                new_idx = current_idx
                meta["consecutive_clean_epochs"] = clean

        new_level = levels[new_idx]
        meta["trust_level"] = new_level

        event = LedgerEvent(
            event_id=event_id,
            ts_utc=ts_utc,
            agent_id=agent_id,
            epoch=epoch_id,
            action="trust_transition",
            risk_profile="LOW",
            trust_level=current_level,
            budget_before={"trust_level": current_level},
            budget_delta={"trust_level_changed": current_level != new_level},
            budget_after={"trust_level": new_level},
        )
        self.append_event(event)
        self.save_state_atomic(state)
        return Verdict(True, None, {
            "agent_id": agent_id,
            "old_trust_level": current_level,
            "new_trust_level": new_level,
        })

    # Existing authority points wrappers
    def hook_scheduler_guarded_skill(
        self,
        agent_id: str,
        skill: str,
        risk_profile: str,
        *,
        epoch_id: str,
        event_id: str,
        ts_utc: str,
        tokens_used: int = 0,
        external_calls_used: int = 0,
    ) -> Verdict:
        return self.enforce_skill_quota(
            agent_id=agent_id,
            skill=skill,
            risk_profile=risk_profile,
            epoch_id=epoch_id,
            event_id=event_id,
            ts_utc=ts_utc,
            tokens_used=tokens_used,
            external_calls_used=external_calls_used,
        )

    def hook_create_governed_commit(
        self,
        agent_id: str,
        *,
        epoch_id: str,
        event_id: str,
        ts_utc: str,
    ) -> Verdict:
        return self.enforce_skill_quota(
            agent_id=agent_id,
            skill="git_commit",
            risk_profile="MEDIUM",
            epoch_id=epoch_id,
            event_id=event_id,
            ts_utc=ts_utc,
            tokens_used=0,
            external_calls_used=0,
        )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aiosctl budgets", description="Read-only budget/trust inspection commands")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--ledger-root", required=False)

    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--epoch", required=True)

    trust = sub.add_parser("trust")
    trust.add_argument("--epoch", required=True)
    trust.add_argument("--agent-id", required=False)

    verify = sub.add_parser("ledger-verify")
    verify.add_argument("--epoch", required=True)

    risk = sub.add_parser("risk-summary")
    risk.add_argument("--epoch", required=True)

    quota = sub.add_parser("quota-status")
    quota.add_argument("--epoch", required=True)
    quota.add_argument("--agent-id", required=False)

    args = parser.parse_args(argv)
    ledger_root = Path(args.ledger_root) if args.ledger_root else None

    try:
        engine = BudgetEngine(Path(args.policy), Path(args.state), ledger_root)
        chain = engine.verify_chain(args.epoch)
        if not chain.ok:
            _print_json({"status": "rejected", "reason_code": chain.reason_code, "data": chain.data})
            return 2

        state = engine.load_state()

        if args.command == "status":
            _print_json({"status": "ok", "epoch": args.epoch, "chain": chain.data, "agents": sorted(state["agents"].keys())})
            return 0

        if args.command == "trust":
            out: dict[str, Any] = {"epoch": args.epoch, "chain": chain.data, "agents": {}}
            for agent_id in sorted(state["agents"].keys()):
                if args.agent_id and args.agent_id != agent_id:
                    continue
                agent = state["agents"][agent_id]
                out["agents"][agent_id] = {
                    "trust_level": agent["meta"]["trust_level"],
                    "consecutive_clean_epochs": agent["meta"]["consecutive_clean_epochs"],
                    "forced_escalations": agent["meta"]["forced_escalations"],
                }
            _print_json(out)
            return 0

        if args.command == "ledger-verify":
            _print_json({"status": "ok", "epoch": args.epoch, "chain": chain.data})
            return 0

        if args.command == "risk-summary":
            out: dict[str, Any] = {"epoch": args.epoch, "chain": chain.data, "agents": {}}
            for agent_id in sorted(state["agents"].keys()):
                ep = state["agents"][agent_id]["epochs"].get(args.epoch, {
                    "skill_used": {},
                    "violations": 0,
                    "high_risk_overflow": 0,
                    "hash_inconsistency": False,
                })
                out["agents"][agent_id] = {
                    "violations": ep["violations"],
                    "high_risk_overflow": ep["high_risk_overflow"],
                    "hash_inconsistency": ep["hash_inconsistency"],
                }
            _print_json(out)
            return 0

        if args.command == "quota-status":
            out: dict[str, Any] = {"epoch": args.epoch, "chain": chain.data, "agents": {}}
            for agent_id in sorted(state["agents"].keys()):
                if args.agent_id and args.agent_id != agent_id:
                    continue
                agent = state["agents"][agent_id]
                trust_level = agent["meta"]["trust_level"]
                ep = agent["epochs"].get(args.epoch, {
                    "skill_used": {},
                    "violations": 0,
                    "high_risk_overflow": 0,
                    "hash_inconsistency": False,
                })
                skill_rows: dict[str, Any] = {}
                for skill, cfg in sorted(engine.policy["skill_quotas"].items()):
                    limit_low_risk = engine.calculate_effective_quota(
                        int(cfg["base_limit"]),
                        trust_level,
                        "LOW",
                        agent_id=agent_id,
                        current_epoch=args.epoch,
                        state=state,
                    )
                    skill_rows[skill] = {
                        "used": int(ep["skill_used"].get(skill, 0)),
                        "base_limit": int(cfg["base_limit"]),
                        "effective_limit_low_risk": limit_low_risk,
                    }
                out["agents"][agent_id] = {
                    "trust_level": trust_level,
                    "skills": skill_rows,
                }
            _print_json(out)
            return 0

        _print_json({"status": "rejected", "reason_code": DENY_STATE_INVALID, "detail": "unknown_command"})
        return 2
    except BudgetError as exc:
        _print_json({"status": "rejected", "reason_code": exc.reason_code, "detail": exc.detail})
        return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())

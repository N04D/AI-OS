import hashlib
import json
import os
import re
import time


class GovernanceViolation(Exception):
    """Raised when a governance enforcement check fails."""


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append_jsonl(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def _extract_allowed_files(instruction_text):
    """
    Extract explicitly referenced repository file paths from instructions.
    Paths are recognized only when wrapped in backticks.
    """
    return set(re.findall(r"`([A-Za-z0-9_.\\-/]+)`", instruction_text))


class GovernanceEnforcer:
    def __init__(
        self,
        governance_path="docs/governance.md",
        environment_path="agents/state/environment.json",
        violation_log_path="logs/governance_violations.log",
    ):
        self.governance_path = governance_path
        self.environment_path = environment_path
        self.violation_log_path = violation_log_path
        self._governance_hash = None
        self._governance_text = None
        self._environment = None
        self.last_report = {
            "governance_compliant": True,
            "violations": [],
            "enforcement_actions": [],
        }

    def _record_violation(self, rule, message, context=None):
        payload = {
            "timestamp": _utc_timestamp(),
            "severity": "critical",
            "rule": rule,
            "message": message,
            "context": context or {},
        }
        self.last_report["governance_compliant"] = False
        self.last_report["violations"].append(payload)
        self.last_report["enforcement_actions"].append("task_rejected")
        _append_jsonl(self.violation_log_path, payload)
        print(f"CRITICAL GOVERNANCE VIOLATION: {message}")

    def _reset_report(self):
        self.last_report = {
            "governance_compliant": True,
            "violations": [],
            "enforcement_actions": [],
        }

    def load_context(self):
        """
        Context Loading gate:
        MUST load docs/governance.md and agents/state/environment.json at startup.
        """
        self._reset_report()
        try:
            with open(self.governance_path, "r", encoding="utf-8") as f:
                self._governance_text = f.read()
            with open(self.environment_path, "r", encoding="utf-8") as f:
                self._environment = json.load(f)
        except Exception as e:
            self._record_violation(
                rule="context_loading",
                message=f"Failed to load governance context: {e}",
            )
            raise GovernanceViolation("Context loading failed")

        self._governance_hash = _sha256_text(self._governance_text)
        return {
            "governance_hash": self._governance_hash,
            "environment_loaded": True,
        }

    def enforce_immutability(self):
        """
        Immutability gate:
        Governance Contract must remain immutable during runtime.
        """
        if self._governance_hash is None:
            self._record_violation(
                rule="immutability",
                message="Governance context was not loaded before enforcement",
            )
            raise GovernanceViolation("Governance context missing")

        try:
            with open(self.governance_path, "r", encoding="utf-8") as f:
                current_hash = _sha256_text(f.read())
        except Exception as e:
            self._record_violation(
                rule="immutability",
                message=f"Cannot verify governance immutability: {e}",
            )
            raise GovernanceViolation("Cannot verify governance immutability")

        if current_hash != self._governance_hash:
            self._record_violation(
                rule="immutability",
                message="Governance Contract changed after startup without amendment flow",
                context={"governance_path": self.governance_path},
            )
            raise GovernanceViolation("Governance Contract mutation detected")

    def validate_instruction(self, instruction_text):
        """
        Instruction Validation gate:
        role separation, allowed actions, and deterministic behavior checks.
        """
        lower = instruction_text.lower()

        role_separation_patterns = [
            r"\bplanner\b.{0,40}\b(write|implement|code|refactor|modify)\b",
            r"\bplanner\b.{0,40}\b(commit|push|execute)\b",
        ]
        for pattern in role_separation_patterns:
            if re.search(pattern, lower, flags=re.DOTALL):
                self._record_violation(
                    rule="role_separation",
                    message="Instruction violates role separation for PLANNER",
                    context={"pattern": pattern},
                )
                raise GovernanceViolation("Instruction validation failed")

        forbidden_action_patterns = [
            r"\buncontrolled architectural\b",
            r"\barchitectural rewrite\b",
            r"\brewrite (the )?(entire|whole)\b",
            r"\bspeculative rewrite\b",
        ]
        for pattern in forbidden_action_patterns:
            if re.search(pattern, lower):
                self._record_violation(
                    rule="allowed_actions",
                    message="Instruction requests forbidden architectural action",
                    context={"pattern": pattern},
                )
                raise GovernanceViolation("Instruction validation failed")

        nondeterministic_terms = [
            "maybe",
            "perhaps",
            "if possible",
            "as needed",
            "when convenient",
        ]
        for term in nondeterministic_terms:
            if term in lower:
                self._record_violation(
                    rule="deterministic_behavior",
                    message="Instruction contains non-deterministic phrasing",
                    context={"term": term},
                )
                raise GovernanceViolation("Instruction validation failed")

    def validate_pre_computation(self, instruction_text, intended_outcome):
        """
        Pre-computation + atomic gate:
        checks occur before dispatch / irreversible actions.
        """
        self.enforce_immutability()
        self.validate_instruction(instruction_text)
        if not intended_outcome or not intended_outcome.strip():
            self._record_violation(
                rule="pre_computation",
                message="Intended outcome is missing",
            )
            raise GovernanceViolation("Pre-computation validation failed")

    def validate_commit_policy(self, instruction_text, changed_files, commit_message):
        """
        Commit Policy gate:
        review file scope, commit message conventions, and forbidden content.
        """
        self.enforce_immutability()

        allowed_files = _extract_allowed_files(instruction_text)
        if not allowed_files:
            self._record_violation(
                rule="commit_policy.affected_files",
                message="No explicit allowed files found in instruction text",
            )
            raise GovernanceViolation("Commit policy validation failed")

        disallowed = [f for f in changed_files if f not in allowed_files]
        if disallowed:
            self._record_violation(
                rule="commit_policy.affected_files",
                message="Commit includes files not explicitly allowed by task",
                context={"disallowed_files": disallowed},
            )
            raise GovernanceViolation("Commit policy validation failed")

        commit_pattern = r"^(feat|fix|chore)\([^)]+\): .+"
        if not re.match(commit_pattern, commit_message):
            self._record_violation(
                rule="commit_policy.message_format",
                message="Commit message does not follow required convention",
                context={"message": commit_message},
            )
            raise GovernanceViolation("Commit policy validation failed")

        if "docs/governance.md" in changed_files:
            self._record_violation(
                rule="content_compliance",
                message="Commit attempts to modify immutable governance contract",
            )
            raise GovernanceViolation("Commit policy validation failed")

    def compliance_report_block(self):
        """
        Returns a reporting block required by the governance enforcement spec.
        """
        lines = ["## Governance Compliance Report"]
        lines.append(
            f"- governance_compliant: {str(self.last_report['governance_compliant']).lower()}"
        )
        if self.last_report["violations"]:
            lines.append(f"- violations_detected: {len(self.last_report['violations'])}")
        else:
            lines.append("- violations_detected: 0")

        if self.last_report["enforcement_actions"]:
            actions = ", ".join(self.last_report["enforcement_actions"])
            lines.append(f"- enforcement_actions: {actions}")
        else:
            lines.append("- enforcement_actions: none")
        return "\n".join(lines)

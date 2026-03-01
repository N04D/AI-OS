import unittest
from pathlib import Path


class GiteaWorkflowContractTests(unittest.TestCase):
    def test_workflow_exists_and_has_required_contract(self):
        workflow = Path(".gitea/workflows/pr-gate.yml")
        self.assertTrue(workflow.exists(), "Expected .gitea/workflows/pr-gate.yml to exist")

        content = workflow.read_text(encoding="utf-8")

        self.assertIn("pull_request:", content)
        self.assertIn("name: pr-gate/path-allowlist", content)
        self.assertIn("name: pr-gate/path-allowlist-contracts", content)
        self.assertIn("python scripts/pr_gate_path_allowlist.py", content)
        self.assertIn("--policy \".gitea/governance/path-allowlist.v1.yaml\"", content)
        self.assertIn("bash scripts/test-pr-gate-m1.sh", content)
        self.assertIn("if [ -z \"${PR_GATE_TOKEN:-}\" ]; then", content)
        self.assertIn("DENY_WORKFLOW_MISSING_TOKEN", content)
        self.assertIn("DENY_WORKFLOW_MISSING_API_BASE", content)
        self.assertIn("if: ${{ always() }}", content)
        self.assertIn("cat gate-verdict.json", content)
        self.assertIn("uses: actions/checkout@v4", content)

    def test_workflow_deny_verdict_schema_contract(self):
        workflow = Path(".gitea/workflows/pr-gate.yml")
        self.assertTrue(workflow.exists(), "Expected .gitea/workflows/pr-gate.yml to exist")
        content = workflow.read_text(encoding="utf-8")

        # Workflow-level fail-closed helper must emit a deterministic verdict shape.
        self.assertIn("write_workflow_deny()", content)
        self.assertIn("\"allow\": false", content)
        self.assertIn("\"reason_code\": \"${reason}\"", content)
        self.assertIn("\"violations\": []", content)
        self.assertIn("\"matched_rule_ids\": []", content)
        self.assertIn("\"policy_sha\": \"\"", content)
        self.assertIn("\"evaluated_at\": \"${ts}\"", content)


if __name__ == "__main__":
    unittest.main()

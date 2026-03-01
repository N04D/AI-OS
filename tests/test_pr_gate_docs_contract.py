import unittest
from pathlib import Path


class PrGateDocsContractTests(unittest.TestCase):
    def test_gitea_setup_doc_has_required_check_and_reason_codes(self):
        doc = Path("docs/gitea-ci-setup.md")
        self.assertTrue(doc.exists(), "Expected docs/gitea-ci-setup.md to exist")
        content = doc.read_text(encoding="utf-8")

        self.assertIn("pr-gate/path-allowlist", content)
        self.assertIn("pr-gate/path-allowlist-contracts", content)
        self.assertIn("DENY_WORKFLOW_MISSING_TOKEN", content)
        self.assertIn("DENY_WORKFLOW_MISSING_API_BASE", content)
        self.assertIn("DENY_POLICY_MISSING", content)
        self.assertIn("DENY_POLICY_PARSE_ERROR", content)

    def test_workflow_and_docs_share_required_check_name(self):
        workflow = Path(".gitea/workflows/pr-gate.yml")
        doc = Path("docs/gitea-ci-setup.md")
        self.assertTrue(workflow.exists(), "Expected .gitea/workflows/pr-gate.yml to exist")
        self.assertTrue(doc.exists(), "Expected docs/gitea-ci-setup.md to exist")

        w = workflow.read_text(encoding="utf-8")
        d = doc.read_text(encoding="utf-8")
        required = "pr-gate/path-allowlist"

        self.assertIn(f"name: {required}", w)
        self.assertIn(required, d)


if __name__ == "__main__":
    unittest.main()

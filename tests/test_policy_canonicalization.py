import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


class PolicyCanonicalizationTests(unittest.TestCase):
    def test_language_policy_canonicalizes_internal_comments_to_report_language(self):
        policy_path = REPO_ROOT / ".claude/policies/language-policy.yaml"
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))

        self.assertEqual(policy["version"], 1)
        self.assertEqual(policy["decision_status"], "approved")
        self.assertEqual(policy["redlines"]["language"], "contract_language")
        self.assertEqual(policy["external_comments"]["language"], "contract_language")
        self.assertEqual(policy["internal_comments"]["language"], "report_language")
        self.assertEqual(policy["analysis_report"]["language"], "report_language")
        self.assertEqual(policy["terminal_output"]["language"], "user_prompt_language")

    def test_default_review_mode_policy_keeps_existing_modes_and_adds_audience_scopes(self):
        policy_path = REPO_ROOT / "contract-review/library/policies.default/review-mode.yaml"
        policy_text = policy_path.read_text(encoding="utf-8")
        policy = yaml.safe_load(policy_text)

        self.assertEqual(policy["policy_version"], 2)
        self.assertEqual(policy["default_mode"], "moderate")
        self.assertEqual(set(policy["modes"].keys()), {"strict", "moderate", "loose"})
        self.assertIn("canonical default policy", policy_text)
        self.assertIn("Markdown tables", policy_text)

        strict = policy["modes"]["strict"]
        moderate = policy["modes"]["moderate"]
        loose = policy["modes"]["loose"]

        self.assertEqual(strict["external_comment_scope"], ["critical", "high", "medium"])
        self.assertEqual(strict["internal_comment_scope"], ["critical", "high", "medium", "low"])
        self.assertEqual(moderate["external_comment_scope"], ["critical", "high"])
        self.assertEqual(moderate["internal_comment_scope"], ["critical", "high", "medium"])
        self.assertEqual(loose["external_comment_scope"], ["critical"])
        self.assertEqual(loose["internal_comment_scope"], ["critical", "high"])

    def test_prompt_docs_reference_canonical_language_policy(self):
        command_text = (REPO_ROOT / ".claude/commands/contract-review.md").read_text(encoding="utf-8")
        agent_text = (REPO_ROOT / ".claude/agents/review-agent/AGENT.md").read_text(encoding="utf-8")
        skill_text = (REPO_ROOT / ".claude/skills/review-domain-knowledge/SKILL.md").read_text(encoding="utf-8")

        for text in (command_text, agent_text, skill_text):
            self.assertIn(".claude/policies/language-policy.yaml", text)

        self.assertNotIn("internal comments in the user's prompt language", command_text)
        self.assertNotIn("Written in the user's prompt language", command_text)
        self.assertNotIn("Comments (Step 9 `[EXTERNAL]` / `[INTERNAL]`): in the contract's original language", agent_text)

    def test_prompt_docs_reference_review_mode_v2_scopes(self):
        command_text = (REPO_ROOT / ".claude/commands/contract-review.md").read_text(encoding="utf-8")
        agent_text = (REPO_ROOT / ".claude/agents/review-agent/AGENT.md").read_text(encoding="utf-8")
        skill_text = (REPO_ROOT / ".claude/skills/review-domain-knowledge/SKILL.md").read_text(encoding="utf-8")

        for text in (agent_text, skill_text):
            self.assertIn("external_comment_scope", text)
            self.assertIn("internal_comment_scope", text)
            self.assertIn("redline_scope", text)
            self.assertIn("contract-review/library/policies.default/review-mode.yaml", text)

        for text in (command_text, agent_text, skill_text):
            self.assertIn("contract-review/library/policies/review-mode.yaml", text)

        self.assertIn("Summary only", skill_text)
        self.assertIn("Do not derive thresholds from this table", skill_text)
        self.assertIn("Do not infer ad hoc thresholds", agent_text)


if __name__ == "__main__":
    unittest.main()

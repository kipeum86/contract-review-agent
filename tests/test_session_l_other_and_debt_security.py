import importlib.util
import json
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


query_module = load_module("query_index_session_l", ".claude/skills/index-manager/scripts/query-index.py")
coverage_module = load_module(
    "report_coverage_session_l",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)
validate_package_module = load_module(
    "validate_package_session_l",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionLOtherAndDebtSecurityTests(unittest.TestCase):
    def test_other_seed_validates_cleanly_and_is_exactly_queryable(self):
        package_dir = REPO_ROOT / "contract-review/library/approved/templates/other/0-other-amendment-general-seed"
        result = validate_package_module.validate_package(str(package_dir))

        self.assertTrue(result["valid"])
        self.assertEqual(result["hard_fails"], [])
        self.assertEqual(result["soft_fails"], [])

        query_result = query_module.query(
            contract_family="other",
            target_clauses=[{"clause_type": "amendment"}],
        )
        self.assertFalse(query_result["general_review_mode"])
        candidate = query_result["candidates"]["amendment"][0]
        self.assertEqual(candidate["doc_id"], "0-other-amendment-general-seed")
        self.assertEqual(candidate["family_match_type"], "exact")
        self.assertEqual(candidate["priority_bucket"], "acceptable_template")
        self.assertEqual(candidate["doc_class"], "template")

    def test_coverage_report_has_full_family_coverage_and_zero_unmapped(self):
        report = coverage_module.generate_report()

        self.assertEqual(report["configured_family_count"], 29)
        self.assertEqual(report["covered_family_count"], 29)
        self.assertEqual(report["uncovered_families"], [])
        self.assertEqual(report["total_unmapped_clause_count"], 0)
        self.assertEqual(report["top_unmapped_headings"], [])

        per_family = {entry["contract_family"]: entry for entry in report["per_family"]}
        self.assertTrue(per_family["other"]["has_library_coverage"])
        self.assertEqual(per_family["other"]["document_count"], 1)
        self.assertEqual(per_family["other"]["clause_count"], 9)

    def test_ssa_bond_issuance_clauses_use_debt_security_issuance_type(self):
        expected_doc_ids = {
            "1-3-1-early-investment-convertible-bond",
            "1-3-2-early-investment-bond-with-warrants",
            "2-3-1-mid-investment-convertible-bond",
            "2-3-2-mid-investment-bond-with-warrants",
            "3-3-1-late-investment-convertible-bond",
            "3-3-2-late-investment-bond-with-warrants",
        }

        query_result = query_module.query(
            contract_family="ssa",
            target_clauses=[{"clause_type": "debt_security_issuance"}],
        )
        self.assertFalse(query_result["general_review_mode"])
        candidates = query_result["candidates"]["debt_security_issuance"]
        self.assertEqual({candidate["doc_id"] for candidate in candidates}, expected_doc_ids)
        self.assertTrue(all(candidate["clause_type"] == "debt_security_issuance" for candidate in candidates))
        self.assertTrue(all(candidate["family_match_type"] == "exact" for candidate in candidates))

        for doc_id in expected_doc_ids:
            clause_path = (
                REPO_ROOT
                / "contract-review/library/approved/templates/ssa"
                / doc_id
                / "clauses/clause-002.json"
            )
            payload = json.loads(clause_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["heading"], "사채의 발행 사항")
            self.assertEqual(payload["clause_type"], "debt_security_issuance")

    def test_taxonomy_and_guides_cover_other_and_debt_security_cases(self):
        taxonomy = yaml.safe_load(
            (
                REPO_ROOT / "contract-review/library/policies/clause-taxonomy.yaml"
            ).read_text(encoding="utf-8")
        )
        ids = {
            clause_type["id"]
            for category in taxonomy["categories"]
            for clause_type in category["clause_types"]
        }
        self.assertIn("debt_security_issuance", ids)

        drafting_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/drafting-guide.md"
        ).read_text(encoding="utf-8")
        review_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/review-guide.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Debt Security Issuance Terms for CB/BW deals", drafting_guide)
        self.assertIn("Other / 기타 부속합의서", drafting_guide)
        self.assertIn("Convertible bond / bond-with-warrants issuance terms omit allocation", review_guide)
        self.assertIn("Other / Amendments / Side Letters", review_guide)


if __name__ == "__main__":
    unittest.main()

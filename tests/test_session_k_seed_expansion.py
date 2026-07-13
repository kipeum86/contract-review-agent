import importlib.util
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


query_module = load_module("query_index_session_k", ".claude/skills/index-manager/scripts/query-index.py")
coverage_module = load_module(
    "report_coverage_session_k",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)
validate_package_module = load_module(
    "validate_package_session_k",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionKSeedExpansionTests(unittest.TestCase):
    def test_apa_and_joint_venture_seeds_include_core_structural_protections(self):
        apa_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/apa/0-apa-business-transfer-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")
        jv_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/joint_venture/0-joint-venture-equity-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")

        self.assertIn("승계 채무", apa_text)
        self.assertIn("전환지원", apa_text)
        self.assertIn("출자 및 자금조달", jv_text)
        self.assertIn("교착상태 해결", jv_text)

    def test_corporate_complex_seed_packages_validate_cleanly(self):
        package_dirs = [
            "contract-review/library/approved/templates/spa/0-spa-share-purchase-seed",
            "contract-review/library/approved/templates/apa/0-apa-business-transfer-seed",
            "contract-review/library/approved/templates/joint_venture/0-joint-venture-equity-seed",
            "contract-review/library/approved/templates/merger/0-merger-absorption-seed",
        ]

        for package_dir in package_dirs:
            with self.subTest(package_dir=package_dir):
                result = validate_package_module.validate_package(str(REPO_ROOT / package_dir))
                self.assertTrue(result["valid"])
                self.assertEqual(result["hard_fails"], [])
                self.assertEqual(result["soft_fails"], [])

    def test_coverage_report_lists_corporate_complex_seed_families(self):
        report = coverage_module.generate_report()

        # Fresh clones ship 26 deterministic seed families; local libraries may add more.
        self.assertGreaterEqual(report["covered_family_count"], 26)
        for family in {"spa", "apa", "joint_venture", "merger"}:
            self.assertIn(family, report["covered_families"])

        per_family = {entry["contract_family"]: entry for entry in report["per_family"]}
        self.assertEqual(per_family["spa"]["clause_count"], 12)
        self.assertEqual(per_family["apa"]["clause_count"], 11)
        self.assertEqual(per_family["joint_venture"]["clause_count"], 11)
        self.assertEqual(per_family["merger"]["clause_count"], 11)

    def test_query_returns_corporate_complex_candidates_with_template_priority_bucket(self):
        scenarios = [
            ("spa", "reps_warranties_seller", "0-spa-share-purchase-seed"),
            ("apa", "transferred_assets", "0-apa-business-transfer-seed"),
            ("joint_venture", "deadlock_resolution", "0-joint-venture-equity-seed"),
            ("merger", "closing_mechanics", "0-merger-absorption-seed"),
        ]

        for family, clause_type, expected_doc_id in scenarios:
            with self.subTest(contract_family=family, clause_type=clause_type):
                result = query_module.query(
                    contract_family=family,
                    target_clauses=[{"clause_type": clause_type}],
                )

                self.assertFalse(result["general_review_mode"])
                candidate = result["candidates"][clause_type][0]
                self.assertEqual(candidate["doc_id"], expected_doc_id)
                self.assertEqual(candidate["family_match_type"], "exact")
                self.assertEqual(candidate["priority_bucket"], "acceptable_template")
                self.assertEqual(candidate["doc_class"], "template")

    def test_taxonomy_and_affinity_include_corporate_complex_supporting_types(self):
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
        for clause_type_id in {
            "capital_contributions",
            "transferred_assets",
            "assumed_liabilities",
            "deadlock_resolution",
        }:
            self.assertIn(clause_type_id, ids)

        priority_policy = yaml.safe_load(
            (
                REPO_ROOT / "contract-review/library/policies/retrieval-priority.yaml"
            ).read_text(encoding="utf-8")
        )
        affinity_groups = priority_policy["filter_rules"]["stage_3_affinity"]["affinity_groups"]
        self.assertIn(["spa", "ssa", "sha", "safe", "apa", "merger", "joint_venture"], affinity_groups)

    def test_guides_cover_corporate_complex_families(self):
        drafting_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/drafting-guide.md"
        ).read_text(encoding="utf-8")
        review_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/review-guide.md"
        ).read_text(encoding="utf-8")

        self.assertIn("APA / 영업양수도 · 자산양수도계약", drafting_guide)
        self.assertIn("Joint Venture / 합작투자계약", drafting_guide)
        self.assertIn("Merger / 합병계약", drafting_guide)
        self.assertIn("Asset Purchase Agreements (영업양수도 · 자산양수도계약)", review_guide)
        self.assertIn("Joint Venture Contracts (합작투자계약)", review_guide)
        self.assertIn("Merger Agreements (합병계약)", review_guide)


if __name__ == "__main__":
    unittest.main()

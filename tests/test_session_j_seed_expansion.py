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


query_module = load_module("query_index_session_j", ".claude/skills/index-manager/scripts/query-index.py")
coverage_module = load_module(
    "report_coverage_session_j",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)
validate_package_module = load_module(
    "validate_package_session_j",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionJSeedExpansionTests(unittest.TestCase):
    def test_marketing_and_settlement_seeds_include_family_specific_protections(self):
        marketing_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/marketing/0-marketing-influencer-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")
        settlement_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/settlement/0-settlement-commercial-dispute-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")

        self.assertIn("광고성 게시물에는 필요한 고지를 명확히 표시", marketing_text)
        self.assertIn("독점", marketing_text)
        self.assertIn("청구권의 포기 및 해제", settlement_text)
        self.assertIn("부제소 합의", settlement_text)
        self.assertIn("책임 불인정", settlement_text)

    def test_fourth_wave_seed_packages_validate_cleanly(self):
        package_dirs = [
            "contract-review/library/approved/templates/publishing/0-publishing-digital-rights-seed",
            "contract-review/library/approved/templates/game_development/0-game-development-publishing-seed",
            "contract-review/library/approved/templates/marketing/0-marketing-influencer-seed",
            "contract-review/library/approved/templates/mou/0-mou-business-cooperation-seed",
            "contract-review/library/approved/templates/loi/0-loi-acquisition-seed",
            "contract-review/library/approved/templates/settlement/0-settlement-commercial-dispute-seed",
        ]

        for package_dir in package_dirs:
            with self.subTest(package_dir=package_dir):
                result = validate_package_module.validate_package(str(REPO_ROOT / package_dir))
                self.assertTrue(result["valid"])
                self.assertEqual(result["hard_fails"], [])
                self.assertEqual(result["soft_fails"], [])

    def test_coverage_report_lists_fourth_wave_seed_families(self):
        report = coverage_module.generate_report()

        self.assertGreaterEqual(report["covered_family_count"], 24)
        for family in {
            "publishing",
            "game_development",
            "marketing",
            "mou",
            "loi",
            "settlement",
        }:
            self.assertIn(family, report["covered_families"])

        per_family = {entry["contract_family"]: entry for entry in report["per_family"]}
        self.assertEqual(per_family["publishing"]["clause_count"], 13)
        self.assertEqual(per_family["game_development"]["clause_count"], 14)
        self.assertEqual(per_family["marketing"]["clause_count"], 12)
        self.assertEqual(per_family["mou"]["clause_count"], 10)
        self.assertEqual(per_family["loi"]["clause_count"], 10)
        self.assertEqual(per_family["settlement"]["clause_count"], 10)

    def test_query_returns_fourth_wave_candidates_with_template_priority_bucket(self):
        scenarios = [
            ("publishing", "grant_of_rights", "0-publishing-digital-rights-seed"),
            ("game_development", "development_milestones", "0-game-development-publishing-seed"),
            ("marketing", "compliance_with_laws", "0-marketing-influencer-seed"),
            ("mou", "binding_effect", "0-mou-business-cooperation-seed"),
            ("loi", "no_shop", "0-loi-acquisition-seed"),
            ("settlement", "release_of_claims", "0-settlement-commercial-dispute-seed"),
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

    def test_taxonomy_and_affinity_include_fourth_wave_supporting_types(self):
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
            "release_of_claims",
            "covenant_not_to_sue",
            "no_admission",
            "non_disparagement",
        }:
            self.assertIn(clause_type_id, ids)

        priority_policy = yaml.safe_load(
            (
                REPO_ROOT / "contract-review/library/policies/retrieval-priority.yaml"
            ).read_text(encoding="utf-8")
        )
        affinity_groups = priority_policy["filter_rules"]["stage_3_affinity"]["affinity_groups"]
        self.assertIn(["services", "independent_contractor", "sow", "marketing"], affinity_groups)

    def test_guides_cover_fourth_wave_families(self):
        drafting_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/drafting-guide.md"
        ).read_text(encoding="utf-8")
        review_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/review-guide.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Marketing / 마케팅 · 광고계약", drafting_guide)
        self.assertIn("MOU / 양해각서", drafting_guide)
        self.assertIn("LOI / 의향서", drafting_guide)
        self.assertIn("Settlement / 합의서", drafting_guide)
        self.assertIn("Publishing Contracts (출판계약)", review_guide)
        self.assertIn("Game Development Contracts (게임개발계약)", review_guide)
        self.assertIn("Marketing Contracts (마케팅 · 광고계약)", review_guide)
        self.assertIn("MOU (양해각서)", review_guide)
        self.assertIn("LOI (의향서)", review_guide)
        self.assertIn("Settlement Agreements (합의서)", review_guide)


if __name__ == "__main__":
    unittest.main()

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


query_module = load_module("query_index_session_h", ".claude/skills/index-manager/scripts/query-index.py")
coverage_module = load_module(
    "report_coverage_session_h",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)
validate_package_module = load_module(
    "validate_package_session_h",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionHSeedExpansionTests(unittest.TestCase):
    def test_first_wave_seeds_include_reviewed_protections(self):
        nda_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/nda/0-nda-mutual-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")
        services_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/services/0-services-general-msa-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")
        employment_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/employment/0-employment-full-time-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")
        lease_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/lease/0-lease-office-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")

        self.assertIn("상호 비밀유지의무", nda_text)
        self.assertIn("각 당사자는 상대방으로부터 비밀정보를 수령하는 경우", nda_text)
        self.assertIn("간접손해 배제", services_text)
        self.assertIn("재위탁 제한", services_text)
        self.assertIn("최저임금 이상", employment_text)
        self.assertIn("해고 및 통지", employment_text)
        self.assertIn("전대 및 양도제한", lease_text)
        self.assertIn("잔여 보증금", lease_text)

    def test_second_wave_seed_packages_validate_cleanly(self):
        package_dirs = [
            "contract-review/library/approved/templates/license/0-license-software-seed",
            "contract-review/library/approved/templates/independent_contractor/0-independent-contractor-seed",
            "contract-review/library/approved/templates/purchase_sales/0-purchase-sales-supply-seed",
            "contract-review/library/approved/templates/saas/0-saas-subscription-seed",
        ]

        for package_dir in package_dirs:
            with self.subTest(package_dir=package_dir):
                result = validate_package_module.validate_package(str(REPO_ROOT / package_dir))
                self.assertTrue(result["valid"])
                self.assertEqual(result["hard_fails"], [])
                self.assertEqual(result["soft_fails"], [])

    def test_coverage_report_lists_second_wave_seed_families(self):
        report = coverage_module.generate_report()

        self.assertGreaterEqual(report["covered_family_count"], 11)
        for family in {"license", "independent_contractor", "purchase_sales", "saas"}:
            self.assertIn(family, report["covered_families"])

        per_family = {entry["contract_family"]: entry for entry in report["per_family"]}
        self.assertEqual(per_family["license"]["clause_count"], 11)
        self.assertEqual(per_family["independent_contractor"]["clause_count"], 11)
        self.assertEqual(per_family["purchase_sales"]["clause_count"], 11)
        self.assertEqual(per_family["saas"]["clause_count"], 12)

    def test_query_returns_second_wave_candidates_with_template_priority_bucket(self):
        scenarios = [
            ("license", "ip_license_grant", "0-license-software-seed"),
            ("independent_contractor", "ip_assignment", "0-independent-contractor-seed"),
            ("purchase_sales", "warranty_period", "0-purchase-sales-supply-seed"),
            ("saas", "data_security", "0-saas-subscription-seed"),
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

    def test_seed_manifests_are_marked_synthetic_interim_baselines(self):
        manifest_paths = [
            REPO_ROOT / "contract-review/library/approved/templates/nda/0-nda-mutual-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/services/0-services-general-msa-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/employment/0-employment-full-time-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/lease/0-lease-office-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/license/0-license-software-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/independent_contractor/0-independent-contractor-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/purchase_sales/0-purchase-sales-supply-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/saas/0-saas-subscription-seed/manifest.yaml",
        ]

        for manifest_path in manifest_paths:
            with self.subTest(manifest_path=manifest_path.name):
                manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                self.assertIn("synthetic-seed", manifest["tags"])
                self.assertIn("Synthetic interim baseline seed package", manifest["notes"])
                self.assertEqual(manifest["authority_level"], "acceptable")

    def test_guides_cover_new_second_wave_families(self):
        drafting_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/drafting-guide.md"
        ).read_text(encoding="utf-8")
        review_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/review-guide.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Independent Contractor / 업무위탁계약", drafting_guide)
        self.assertIn("Purchase & Sales / 물품매매 · 공급계약", drafting_guide)
        self.assertIn("License Contracts (라이선스계약)", review_guide)
        self.assertIn("Independent Contractor Contracts (업무위탁계약)", review_guide)
        self.assertIn("Purchase & Sales / Supply Contracts (물품매매 · 공급계약)", review_guide)


if __name__ == "__main__":
    unittest.main()

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


query_module = load_module("query_index_session_i", ".claude/skills/index-manager/scripts/query-index.py")
coverage_module = load_module(
    "report_coverage_session_i",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)
validate_package_module = load_module(
    "validate_package_session_i",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionISeedExpansionTests(unittest.TestCase):
    def test_privacy_and_dpa_seeds_include_pipa_sensitive_protections(self):
        privacy_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/privacy_policy/0-privacy-policy-general-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")
        dpa_text = (
            REPO_ROOT
            / "contract-review/library/approved/templates/dpa/0-dpa-pipa-seed/normalized/clean.md"
        ).read_text(encoding="utf-8")

        self.assertIn("제3자 제공", privacy_text)
        self.assertIn("국외이전", privacy_text)
        self.assertIn("개인정보 보호책임자", privacy_text)
        self.assertIn("재위탁 제한", dpa_text)
        self.assertIn("점검 및 감사", dpa_text)
        self.assertIn("반환 및 삭제", dpa_text)

    def test_third_wave_seed_packages_validate_cleanly(self):
        package_dirs = [
            "contract-review/library/approved/templates/sow/0-sow-fixed-price-seed",
            "contract-review/library/approved/templates/ip_transfer/0-ip-transfer-copyright-assignment-seed",
            "contract-review/library/approved/templates/content_distribution/0-content-distribution-ott-seed",
            "contract-review/library/approved/templates/tos/0-tos-platform-seed",
            "contract-review/library/approved/templates/eula/0-eula-software-seed",
            "contract-review/library/approved/templates/privacy_policy/0-privacy-policy-general-seed",
            "contract-review/library/approved/templates/dpa/0-dpa-pipa-seed",
        ]

        for package_dir in package_dirs:
            with self.subTest(package_dir=package_dir):
                result = validate_package_module.validate_package(str(REPO_ROOT / package_dir))
                self.assertTrue(result["valid"])
                self.assertEqual(result["hard_fails"], [])
                self.assertEqual(result["soft_fails"], [])

    def test_coverage_report_lists_third_wave_seed_families(self):
        report = coverage_module.generate_report()

        self.assertGreaterEqual(report["covered_family_count"], 18)
        for family in {
            "sow",
            "ip_transfer",
            "content_distribution",
            "tos",
            "eula",
            "privacy_policy",
            "dpa",
        }:
            self.assertIn(family, report["covered_families"])

        per_family = {entry["contract_family"]: entry for entry in report["per_family"]}
        self.assertEqual(per_family["sow"]["clause_count"], 12)
        self.assertEqual(per_family["ip_transfer"]["clause_count"], 10)
        self.assertEqual(per_family["content_distribution"]["clause_count"], 12)
        self.assertEqual(per_family["tos"]["clause_count"], 13)
        self.assertEqual(per_family["eula"]["clause_count"], 12)
        self.assertEqual(per_family["privacy_policy"]["clause_count"], 11)
        self.assertEqual(per_family["dpa"]["clause_count"], 12)

    def test_query_returns_third_wave_candidates_with_template_priority_bucket(self):
        scenarios = [
            ("sow", "milestones", "0-sow-fixed-price-seed"),
            ("ip_transfer", "ip_assignment", "0-ip-transfer-copyright-assignment-seed"),
            ("content_distribution", "grant_of_rights", "0-content-distribution-ott-seed"),
            ("tos", "data_protection", "0-tos-platform-seed"),
            ("eula", "ip_license_grant", "0-eula-software-seed"),
            ("privacy_policy", "data_subject_rights", "0-privacy-policy-general-seed"),
            ("dpa", "sub_processor", "0-dpa-pipa-seed"),
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

    def test_third_wave_seed_manifests_are_marked_synthetic_interim_baselines(self):
        manifest_paths = [
            REPO_ROOT / "contract-review/library/approved/templates/sow/0-sow-fixed-price-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/ip_transfer/0-ip-transfer-copyright-assignment-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/content_distribution/0-content-distribution-ott-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/tos/0-tos-platform-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/eula/0-eula-software-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/privacy_policy/0-privacy-policy-general-seed/manifest.yaml",
            REPO_ROOT / "contract-review/library/approved/templates/dpa/0-dpa-pipa-seed/manifest.yaml",
        ]

        for manifest_path in manifest_paths:
            with self.subTest(manifest_path=manifest_path.name):
                manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                self.assertIn("synthetic-seed", manifest["tags"])
                self.assertIn("Synthetic interim baseline seed package", manifest["notes"])
                self.assertEqual(manifest["authority_level"], "acceptable")

    def test_guides_cover_new_third_wave_families(self):
        drafting_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/drafting-guide.md"
        ).read_text(encoding="utf-8")
        review_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/review-guide.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Statement of Work / 과업지시서", drafting_guide)
        self.assertIn("IP Transfer / 지식재산권 양도계약", drafting_guide)
        self.assertIn("Content Distribution / 콘텐츠 유통 · 배급계약", drafting_guide)
        self.assertIn("Terms of Service / 이용약관", drafting_guide)
        self.assertIn("EULA / 최종사용자 사용권계약", drafting_guide)
        self.assertIn("Privacy Policy / 개인정보처리방침", drafting_guide)
        self.assertIn("Data Processing Agreement / 개인정보 처리위탁계약", drafting_guide)
        self.assertIn("Statement of Work / 과업지시서", review_guide)
        self.assertIn("IP Transfer / Assignment Contracts (지식재산권 양도계약)", review_guide)
        self.assertIn("Content Distribution Contracts (콘텐츠 유통 · 배급계약)", review_guide)
        self.assertIn("Terms of Service (이용약관)", review_guide)
        self.assertIn("EULA (최종사용자 사용권계약)", review_guide)
        self.assertIn("Privacy Policies (개인정보처리방침)", review_guide)
        self.assertIn("Data Processing Agreements (개인정보 처리위탁계약)", review_guide)

    def test_retrieval_affinity_group_includes_dpa(self):
        priority_policy = yaml.safe_load(
            (
                REPO_ROOT / "contract-review/library/policies/retrieval-priority.yaml"
            ).read_text(encoding="utf-8")
        )
        affinity_groups = priority_policy["filter_rules"]["stage_3_affinity"]["affinity_groups"]
        self.assertIn(["tos", "eula", "privacy_policy", "dpa", "saas"], affinity_groups)


if __name__ == "__main__":
    unittest.main()

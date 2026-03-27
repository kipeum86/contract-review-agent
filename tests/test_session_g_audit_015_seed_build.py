import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build_index_module = load_module(
    "build_index_session_g",
    ".claude/skills/index-manager/scripts/build-index.py",
)
query_module = load_module(
    "query_index_session_g",
    ".claude/skills/index-manager/scripts/query-index.py",
)
coverage_module = load_module(
    "report_coverage_session_g",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)
validate_package_module = load_module(
    "validate_package_session_g",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionGAudit015SeedBuildTests(unittest.TestCase):
    def test_build_index_normalized_clause_carries_doc_class(self):
        normalized = build_index_module.normalize_clause_record(
            clause_data={
                "clause_id": "clause-001",
                "clause_type": "confidentiality",
                "heading": "비밀유지",
                "text": "비밀정보를 누설하지 않는다.",
            },
            manifest={
                "doc_id": "seed-doc",
                "doc_class": "template",
                "contract_family": "nda",
                "jurisdiction": "KR",
                "governing_law": "대한민국 법률 (Korean law)",
                "language": "ko",
                "authority_level": "acceptable",
                "approval_state": "approved",
                "status": "active",
                "_manifest_path": str(REPO_ROOT / "contract-review/library/approved/templates/nda/seed/manifest.yaml"),
            },
            clause_path=str(REPO_ROOT / "contract-review/library/approved/templates/nda/seed/clauses/clause-001.json"),
        )

        self.assertEqual(normalized["doc_class"], "template")

    def test_seed_packages_validate_cleanly(self):
        package_dirs = [
            "contract-review/library/approved/templates/nda/0-nda-mutual-seed",
            "contract-review/library/approved/templates/services/0-services-general-msa-seed",
            "contract-review/library/approved/templates/employment/0-employment-full-time-seed",
            "contract-review/library/approved/templates/lease/0-lease-office-seed",
        ]

        for package_dir in package_dirs:
            with self.subTest(package_dir=package_dir):
                result = validate_package_module.validate_package(str(REPO_ROOT / package_dir))
                self.assertTrue(result["valid"])
                self.assertEqual(result["hard_fails"], [])
                self.assertEqual(result["soft_fails"], [])

    def test_coverage_report_lists_new_seed_families(self):
        report = coverage_module.generate_report()

        self.assertGreaterEqual(report["covered_family_count"], 7)
        for family in {"employment", "lease", "nda", "services"}:
            self.assertIn(family, report["covered_families"])

        per_family = {entry["contract_family"]: entry for entry in report["per_family"]}
        self.assertEqual(per_family["nda"]["clause_count"], 9)
        self.assertEqual(per_family["services"]["clause_count"], 13)
        self.assertEqual(per_family["employment"]["clause_count"], 11)
        self.assertEqual(per_family["lease"]["clause_count"], 10)

    def test_query_returns_seed_candidates_with_template_priority_bucket(self):
        scenarios = [
            ("nda", "confidentiality", "0-nda-mutual-seed"),
            ("services", "scope_of_services", "0-services-general-msa-seed"),
            ("employment", "employee_duties", "0-employment-full-time-seed"),
            ("lease", "premises_description", "0-lease-office-seed"),
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


if __name__ == "__main__":
    unittest.main()

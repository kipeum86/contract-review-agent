import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_CALIBRATION_POLICY_PATH = (
    REPO_ROOT / "contract-review/library/policies/seed-calibration-policy.yaml"
)


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


validate_package_module = load_module(
    "validate_package_session_m",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)
calibration_report_module = load_module(
    "report_seed_calibration_session_m",
    "scripts/report_seed_calibration.py",
)


class SessionMSeedCalibrationTests(unittest.TestCase):
    def _write_valid_minimal_package(
        self,
        package_dir: Path,
        *,
        contract_family: str,
        authority_level: str,
        tags: list[str],
        calibration_review: dict | None = None,
    ) -> None:
        (package_dir / "normalized").mkdir(parents=True)
        (package_dir / "structure").mkdir(parents=True)
        (package_dir / "clauses").mkdir(parents=True)
        (package_dir / "quality").mkdir(parents=True)

        (package_dir / "normalized" / "clean.md").write_text(
            "# Sample\n\nContract text.\n",
            encoding="utf-8",
        )
        (package_dir / "normalized" / "plain.txt").write_text(
            "Contract text.\n",
            encoding="utf-8",
        )
        (package_dir / "structure" / "outline.json").write_text(
            json.dumps(
                [
                    {"line": 1, "level": 1, "text": "제1장"},
                    {"line": 2, "level": 2, "text": "제1조"},
                    {"line": 3, "level": 2, "text": "제2조"},
                    {"line": 4, "level": 2, "text": "제3조"},
                    {"line": 5, "level": 2, "text": "제4조"},
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (package_dir / "structure" / "defined_terms.json").write_text(
            json.dumps([{"term": "계약", "first_line": 1}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        manifest = {
            "doc_id": "sample-seed-doc",
            "title": "Sample Synthetic Seed",
            "title_en": "Sample Synthetic Seed",
            "doc_class": "template",
            "contract_family": contract_family,
            "paper_role": "neutral",
            "jurisdiction": "KR",
            "governing_law": "대한민국 법률 (Korean law)",
            "language": "ko",
            "approval_state": "approved",
            "status": "active",
            "classification_confidence": "high",
            "authority_level": authority_level,
            "external_safe": False,
            "freshness_sensitive": False,
            "sha256": "a" * 64,
            "source_file": "sample-seed.md",
            "created_at": "2026-03-27T00:00:00+00:00",
            "updated_at": "2026-03-27T00:00:00+00:00",
            "tags": tags,
        }
        (package_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        for idx in range(1, 6):
            clause = {
                "clause_id": f"clause-{idx:03d}",
                "section_no": f"제{idx}조",
                "heading": f"조항 {idx}",
                "clause_type": "confidentiality" if idx == 1 else "amendment",
                "text": f"(조항 {idx}) 본 계약의 조항 {idx} 본문",
                "defined_terms_used": ["계약"],
                "cross_refs": [],
                "paragraph_count": 1,
            }
            (package_dir / "clauses" / f"clause-{idx:03d}.json").write_text(
                json.dumps(clause, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        if calibration_review is not None:
            (package_dir / "quality" / "calibration-review.json").write_text(
                json.dumps(calibration_review, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def test_generated_synthetic_seeds_include_calibration_review_metadata(self):
        package_dirs = [
            REPO_ROOT / "contract-review/library/approved/templates/nda/0-nda-mutual-seed",
            REPO_ROOT / "contract-review/library/approved/templates/other/0-other-amendment-general-seed",
        ]

        for package_dir in package_dirs:
            with self.subTest(package_dir=package_dir.name):
                manifest = yaml.safe_load((package_dir / "manifest.yaml").read_text(encoding="utf-8"))
                calibration = json.loads(
                    (package_dir / "quality/calibration-review.json").read_text(encoding="utf-8")
                )
                result = validate_package_module.validate_package(str(package_dir))

                self.assertIn("synthetic-seed", manifest["tags"])
                self.assertTrue(result["valid"], result)
                self.assertEqual(result["hard_fails"], [])
                self.assertEqual(result["soft_fails"], [])
                self.assertEqual(calibration["current_authority_level"], manifest["authority_level"])
                self.assertEqual(calibration["external_domain_review_status"], "pending")
                self.assertEqual(calibration["promotion_recommendation"], "keep_acceptable")
                self.assertEqual(
                    calibration["promotion_blockers"],
                    ["external_domain_expert_review_pending"],
                )

    def test_validator_rejects_preferred_synthetic_seed_without_completed_external_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            self._write_valid_minimal_package(
                package_dir,
                contract_family="nda",
                authority_level="preferred",
                tags=["synthetic-seed"],
                calibration_review={
                    "doc_id": "sample-seed-doc",
                    "package_kind": "synthetic_seed",
                    "contract_family": "nda",
                    "current_authority_level": "preferred",
                    "internal_review_status": "complete",
                    "external_domain_review_status": "pending",
                    "promotion_recommendation": "keep_acceptable",
                    "promotion_blockers": ["external_domain_expert_review_pending"],
                    "external_review": {
                        "reviewer_name": None,
                        "reviewer_role": None,
                        "reviewed_at": None,
                    },
                },
            )

            result = validate_package_module.validate_package(str(package_dir))

            self.assertFalse(result["valid"], result)
            self.assertIn(
                "Synthetic seed cannot use authority_level=preferred without completed external domain review",
                result["hard_fails"],
            )
            self.assertIn(
                "Synthetic seed cannot use authority_level=preferred without promote_to_preferred recommendation",
                result["hard_fails"],
            )

    def test_calibration_report_summarizes_pending_and_violation_states(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir) / "approved" / "templates"

            good_package = templates_dir / "nda" / "0-nda-seed"
            self._write_valid_minimal_package(
                good_package,
                contract_family="nda",
                authority_level="acceptable",
                tags=["synthetic-seed"],
                calibration_review={
                    "doc_id": "sample-seed-doc",
                    "package_kind": "synthetic_seed",
                    "contract_family": "nda",
                    "current_authority_level": "acceptable",
                    "internal_review_status": "complete",
                    "external_domain_review_status": "pending",
                    "promotion_recommendation": "keep_acceptable",
                    "promotion_blockers": ["external_domain_expert_review_pending"],
                    "external_review": {
                        "reviewer_name": None,
                        "reviewer_role": None,
                        "reviewed_at": None,
                    },
                },
            )

            violating_package = templates_dir / "license" / "0-license-seed"
            self._write_valid_minimal_package(
                violating_package,
                contract_family="license",
                authority_level="preferred",
                tags=["synthetic-seed"],
                calibration_review={
                    "doc_id": "sample-seed-doc",
                    "package_kind": "synthetic_seed",
                    "contract_family": "license",
                    "current_authority_level": "preferred",
                    "internal_review_status": "complete",
                    "external_domain_review_status": "pending",
                    "promotion_recommendation": "keep_acceptable",
                    "promotion_blockers": ["external_domain_expert_review_pending"],
                    "external_review": {
                        "reviewer_name": None,
                        "reviewer_role": None,
                        "reviewed_at": None,
                    },
                },
            )

            report = calibration_report_module.generate_report(
                approved_templates_dir=templates_dir,
                policy_path=SEED_CALIBRATION_POLICY_PATH,
            )

            self.assertTrue(report["success"])
            self.assertEqual(report["synthetic_seed_count"], 2)
            self.assertEqual(report["packages_missing_calibration_review"], [])
            self.assertEqual(report["external_domain_review_status_counts"]["pending"], 2)
            self.assertEqual(report["promotion_recommendation_counts"]["keep_acceptable"], 2)
            self.assertEqual(len(report["preferred_gate_violations"]), 1)
            self.assertEqual(report["preferred_gate_violations"][0]["contract_family"], "license")
            self.assertEqual(report["ready_for_preferred_promotion"], [])


if __name__ == "__main__":
    unittest.main()

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


packet_builder_module = load_module(
    "build_seed_review_packets_session_n",
    "scripts/build_seed_review_packets.py",
)
calibration_report_module = load_module(
    "report_seed_calibration_session_n",
    "scripts/report_seed_calibration.py",
)
update_calibration_module = load_module(
    "update_seed_calibration_session_n",
    "scripts/update_seed_calibration.py",
)
validate_package_module = load_module(
    "validate_package_session_n",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


def write_minimal_synthetic_package(
    package_dir: Path,
    *,
    contract_family: str,
    authority_level: str = "acceptable",
    external_status: str = "pending",
    recommendation: str = "keep_acceptable",
) -> None:
    (package_dir / "normalized").mkdir(parents=True)
    (package_dir / "structure").mkdir(parents=True)
    (package_dir / "clauses").mkdir(parents=True)
    (package_dir / "quality").mkdir(parents=True)

    manifest = {
        "doc_id": f"0-{contract_family}-seed",
        "title": f"{contract_family} seed",
        "title_en": f"{contract_family} seed",
        "doc_class": "template",
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
        "contract_family": contract_family,
        "subtype": f"{contract_family}_baseline",
        "sha256": "a" * 64,
        "source_file": f"{contract_family}.md",
        "created_at": "2026-03-27T00:00:00+00:00",
        "updated_at": "2026-03-27T00:00:00+00:00",
        "tags": ["seed-baseline", "synthetic-seed"],
        "notes": "Synthetic interim baseline.",
        "industry": "general",
        "stats": {
            "total_clauses": 5,
            "unmapped_clauses": 0,
            "unmapped_ratio": 0.0,
            "defined_terms": 2,
            "sections": 5,
            "exhibits": 0,
        },
    }
    (package_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    (package_dir / "normalized" / "clean.md").write_text(
        "# Header\n\nFull contract text.\n",
        encoding="utf-8",
    )
    (package_dir / "normalized" / "plain.txt").write_text(
        "Full contract text.\n",
        encoding="utf-8",
    )
    (package_dir / "structure" / "outline.json").write_text(
        json.dumps(
            [{"line": idx, "level": 2, "text": f"제{idx}조"} for idx in range(1, 6)],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "structure" / "defined_terms.json").write_text(
        json.dumps(
            [{"term": "당사자", "first_line": 1}, {"term": "계약", "first_line": 2}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for idx in range(1, 6):
        clause = {
            "clause_id": f"clause-{idx:03d}",
            "section_no": f"제{idx}조",
            "heading": f"조항 {idx}",
            "clause_type": "confidentiality" if idx == 1 else "amendment",
            "text": f"조항 {idx} 본문이다.",
            "defined_terms_used": ["계약"],
            "cross_refs": [],
            "paragraph_count": 1,
        }
        (package_dir / "clauses" / f"clause-{idx:03d}.json").write_text(
            json.dumps(clause, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    calibration = {
        "doc_id": manifest["doc_id"],
        "package_kind": "synthetic_seed",
        "contract_family": contract_family,
        "subtype": manifest["subtype"],
        "jurisdiction": "KR",
        "current_authority_level": authority_level,
        "internal_review_status": "complete",
        "external_domain_review_status": external_status,
        "promotion_recommendation": recommendation,
        "promotion_blockers": ["external_domain_expert_review_pending"]
        if external_status == "pending"
        else ["reviewer_kept_as_acceptable"],
        "reviewed_against": ["drafting-guide", "review-guide"],
        "internal_review_completed_at": "2026-03-27T00:00:00+00:00",
        "external_review": {
            "reviewer_name": None,
            "reviewer_role": None,
            "reviewed_at": None,
            "approval_note": None,
        },
        "review_notes": ["Synthetic interim baseline."],
    }
    (package_dir / "quality" / "calibration-review.json").write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_seed_calibration_policy(path: Path) -> None:
    policy = {
        "synthetic_seed": {
            "manifest_tag": "synthetic-seed",
            "calibration_review_path": "quality/calibration-review.json",
            "internal_review_status_values": ["complete"],
            "external_domain_review_status_values": ["pending", "completed", "waived"],
            "promotion_recommendation_values": [
                "keep_acceptable",
                "promote_to_preferred",
                "needs_revision",
                "needs_family_split",
            ],
            "preferred_authority_requires": {
                "external_domain_review_status": "completed",
                "promotion_recommendation": "promote_to_preferred",
                "required_external_review_fields": [
                    "reviewer_name",
                    "reviewer_role",
                    "reviewed_at",
                ],
            },
            "review_execution": {
                "family_priority_order": ["privacy_policy", "nda", "merger"],
                "family_clusters": {
                    "privacy_policy": "data_compliance",
                    "nda": "workforce_and_services",
                    "merger": "corporate_and_transactional",
                },
                "cluster_checklists": {
                    "data_compliance": ["Confirm Korean disclosure baseline."],
                    "workforce_and_services": ["Check scope and liability balance."],
                    "corporate_and_transactional": ["Review approval and closing structure."],
                },
            },
            "promotion_blockers": {
                "pending_external_review": ["external_domain_expert_review_pending"],
                "keep_acceptable": ["reviewer_kept_as_acceptable"],
                "needs_revision": ["revision_required_before_promotion"],
                "needs_family_split": ["family_split_required_before_promotion"],
                "waived_external_review": ["external_review_waived_not_eligible_for_preferred"],
            },
        }
    }
    path.write_text(
        yaml.safe_dump(policy, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


class SessionNReviewExecutionTests(unittest.TestCase):
    def test_report_adds_priority_sorted_pending_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            templates_dir = root / "approved" / "templates"
            policy_path = root / "seed-calibration-policy.yaml"
            write_seed_calibration_policy(policy_path)

            for family in ["merger", "nda", "privacy_policy"]:
                write_minimal_synthetic_package(templates_dir / family / f"0-{family}-seed", contract_family=family)

            report = calibration_report_module.generate_report(
                approved_templates_dir=templates_dir,
                policy_path=policy_path,
            )

            self.assertEqual(
                [item["contract_family"] for item in report["pending_review_queue"]],
                ["privacy_policy", "nda", "merger"],
            )
            self.assertEqual(report["pending_review_queue"][0]["review_cluster"], "data_compliance")
            self.assertEqual(report["pending_review_queue"][1]["review_priority_rank"], 2)

    def test_packet_builder_collects_checklists_and_clause_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            templates_dir = root / "approved" / "templates"
            policy_path = root / "seed-calibration-policy.yaml"
            output_dir = root / "output"
            write_seed_calibration_policy(policy_path)
            package_dir = templates_dir / "nda" / "0-nda-seed"
            write_minimal_synthetic_package(package_dir, contract_family="nda")

            packets = packet_builder_module.collect_seed_packets(
                approved_templates_dir=templates_dir,
                policy_path=policy_path,
                external_status_filter="pending",
                family_filter="nda",
            )

            self.assertEqual(len(packets), 1)
            packet = packets[0]
            self.assertEqual(packet["review_cluster"], "workforce_and_services")
            self.assertEqual(packet["review_checklist"], ["Check scope and liability balance."])
            self.assertEqual(packet["defined_terms"], ["당사자", "계약"])
            self.assertEqual(packet["clauses"][0]["section_no"], "제1조")

            markdown = packet_builder_module.render_packet_markdown(packet, "2026-03-27T00:00:00+00:00")
            queue_markdown = packet_builder_module.build_queue_markdown(packets, "2026-03-27T00:00:00+00:00")
            packet_builder_module.write_text(output_dir / "nda.md", markdown)
            packet_builder_module.write_text(output_dir / "queue.md", queue_markdown)

            self.assertIn("## Review Checklist", markdown)
            self.assertIn("Check scope and liability balance.", markdown)
            self.assertIn("제1조 조항 1 [confidentiality]", markdown)
            self.assertIn("Synthetic Seed Review Queue", queue_markdown)
            self.assertTrue((output_dir / "nda.md").exists())

    def test_update_script_promotes_manifest_after_completed_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            policy_dir = root / "contract-review" / "library" / "policies"
            policy_dir.mkdir(parents=True)
            policy_path = policy_dir / "seed-calibration-policy.yaml"
            write_seed_calibration_policy(policy_path)
            package_dir = root / "contract-review" / "library" / "approved" / "templates" / "nda" / "0-nda-seed"
            write_minimal_synthetic_package(package_dir, contract_family="nda")

            stdout = io.StringIO()
            argv = [
                "update_seed_calibration.py",
                "--package-dir",
                "contract-review/library/approved/templates/nda/0-nda-seed",
                "--external-status",
                "completed",
                "--recommendation",
                "promote_to_preferred",
                "--reviewer-name",
                "Kim Reviewer",
                "--reviewer-role",
                "External Counsel",
                "--reviewed-at",
                "2026-03-27T12:00:00+00:00",
                "--approval-note",
                "Calibrated for preferred use.",
                "--review-note",
                "External review completed with no material drafting gaps.",
                "--promote-manifest",
            ]

            with mock.patch.object(update_calibration_module, "PROJECT_ROOT", root), mock.patch.object(
                update_calibration_module, "POLICY_PATH", policy_path
            ), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                update_calibration_module.main()

            result = json.loads(stdout.getvalue())
            manifest = yaml.safe_load((package_dir / "manifest.yaml").read_text(encoding="utf-8"))
            calibration = json.loads(
                (package_dir / "quality" / "calibration-review.json").read_text(encoding="utf-8")
            )
            validation = validate_package_module.validate_package(str(package_dir))

            self.assertTrue(result["success"])
            self.assertTrue(result["ready_for_preferred_promotion"])
            self.assertEqual(manifest["authority_level"], "preferred")
            self.assertEqual(calibration["promotion_blockers"], [])
            self.assertEqual(calibration["external_domain_review_status"], "completed")
            self.assertEqual(calibration["external_review"]["reviewer_name"], "Kim Reviewer")
            self.assertIn(
                "External review completed with no material drafting gaps.",
                calibration["review_notes"],
            )
            self.assertTrue(validation["valid"], validation)

    def test_update_script_rejects_invalid_preferred_recommendation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            policy_dir = root / "contract-review" / "library" / "policies"
            policy_dir.mkdir(parents=True)
            policy_path = policy_dir / "seed-calibration-policy.yaml"
            write_seed_calibration_policy(policy_path)
            package_dir = root / "contract-review" / "library" / "approved" / "templates" / "nda" / "0-nda-seed"
            write_minimal_synthetic_package(package_dir, contract_family="nda")

            argv = [
                "update_seed_calibration.py",
                "--package-dir",
                "contract-review/library/approved/templates/nda/0-nda-seed",
                "--external-status",
                "pending",
                "--recommendation",
                "promote_to_preferred",
            ]

            with mock.patch.object(update_calibration_module, "PROJECT_ROOT", root), mock.patch.object(
                update_calibration_module, "POLICY_PATH", policy_path
            ), mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as exc:
                    update_calibration_module.main()

            self.assertIn(
                "promote_to_preferred recommendation requires completed external review.",
                str(exc.exception),
            )


if __name__ == "__main__":
    unittest.main()

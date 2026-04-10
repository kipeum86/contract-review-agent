import importlib.util
import tempfile
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


query_module = load_module("query_index_session_e", ".claude/skills/index-manager/scripts/query-index.py")
detect_format_module = load_module(
    "detect_format_session_e",
    ".claude/skills/doc-parser/scripts/detect-format.py",
)
normalize_module = load_module(
    "normalize_session_e",
    ".claude/skills/doc-parser/scripts/normalize.py",
)
coverage_module = load_module(
    "report_coverage_session_e",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)


class SessionEAudit012QueryTests(unittest.TestCase):
    def test_query_applies_language_preference_priority_order_and_affinity_expansion(self):
        original_load_json = query_module.load_json
        original_load_yaml = query_module.load_yaml

        try:
            clauses = [
                {
                    "doc_id": "nda-ko-preferred",
                    "clause_id": "clause-001",
                    "contract_family": "nda",
                    "clause_type": "confidentiality",
                    "doc_class": "template",
                    "authority_level": "preferred",
                    "approval_state": "approved",
                    "status": "active",
                    "language": "ko",
                },
                {
                    "doc_id": "nda-en-preferred",
                    "clause_id": "clause-002",
                    "contract_family": "nda",
                    "clause_type": "confidentiality",
                    "doc_class": "template",
                    "authority_level": "preferred",
                    "approval_state": "approved",
                    "status": "active",
                    "language": "en",
                },
                {
                    "doc_id": "license-ko-preferred",
                    "clause_id": "clause-003",
                    "contract_family": "license",
                    "clause_type": "confidentiality",
                    "doc_class": "template",
                    "authority_level": "preferred",
                    "approval_state": "approved",
                    "status": "active",
                    "language": "ko",
                },
                {
                    "doc_id": "license-ko-acceptable",
                    "clause_id": "clause-004",
                    "contract_family": "license",
                    "clause_type": "confidentiality",
                    "doc_class": "template",
                    "authority_level": "acceptable",
                    "approval_state": "approved",
                    "status": "active",
                    "language": "ko",
                },
            ]
            retrieval_config = {
                "priority_order": {
                    "1": "preferred_template",
                    "2": "acceptable_template",
                    "3": "fallback_template",
                    "4": "approved_precedent",
                    "5": "reference_only",
                },
                "filter_rules": {
                    "stage_1_5": {"trigger_threshold": 50},
                    "stage_3_affinity": {
                        "minimum_exact_candidates": 3,
                        "affinity_groups": [["nda", "license", "services"]],
                        "penalty": 1,
                    },
                },
                "freshness_rules": {
                    "stale_threshold_days": 365,
                    "stale_handling": "downrank",
                },
            }

            def fake_load_json(path):
                if str(path).endswith("clauses.json"):
                    return {"clauses": clauses}
                return None

            query_module.load_json = fake_load_json
            query_module.load_yaml = lambda path: retrieval_config

            result = query_module.query(
                contract_family="nda",
                language="ko",
                target_clauses=[{"clause_type": "confidentiality"}],
            )

            candidates = result["candidates"]["confidentiality"]
            self.assertTrue(result["affinity_expanded"])
            self.assertEqual(result["affinity_families"], ["license", "services"])
            self.assertEqual(
                [candidate["doc_id"] for candidate in candidates],
                [
                    "nda-ko-preferred",
                    "nda-en-preferred",
                    "license-ko-preferred",
                    "license-ko-acceptable",
                ],
            )
            self.assertEqual(
                [candidate["family_match_type"] for candidate in candidates],
                ["exact", "exact", "affinity", "affinity"],
            )
            self.assertEqual(
                [candidate["priority_bucket"] for candidate in candidates],
                [
                    "preferred_template",
                    "preferred_template",
                    "preferred_template",
                    "acceptable_template",
                ],
            )
            self.assertEqual(candidates[0]["language_preference_rank"], 0)
            self.assertEqual(candidates[1]["language_preference_rank"], 2)
        finally:
            query_module.load_json = original_load_json
            query_module.load_yaml = original_load_yaml

    def test_query_downranks_stale_candidates_after_fresh_candidates(self):
        original_load_json = query_module.load_json
        original_load_yaml = query_module.load_yaml

        try:
            clauses = [
                {
                    "doc_id": "fresh-nda",
                    "clause_id": "clause-001",
                    "contract_family": "nda",
                    "clause_type": "confidentiality",
                    "doc_class": "template",
                    "authority_level": "preferred",
                    "approval_state": "approved",
                    "status": "active",
                    "freshness_sensitive": True,
                    "last_legal_refresh_date": "2026-03-01T00:00:00+00:00",
                },
                {
                    "doc_id": "stale-nda",
                    "clause_id": "clause-002",
                    "contract_family": "nda",
                    "clause_type": "confidentiality",
                    "doc_class": "template",
                    "authority_level": "preferred",
                    "approval_state": "approved",
                    "status": "active",
                    "freshness_sensitive": True,
                    "last_legal_refresh_date": "2024-01-01T00:00:00+00:00",
                },
            ]
            retrieval_config = {
                "priority_order": {"1": "preferred_template"},
                "filter_rules": {
                    "stage_1_5": {"trigger_threshold": 50},
                    "stage_3_affinity": {"minimum_exact_candidates": 0, "affinity_groups": []},
                },
                "freshness_rules": {
                    "stale_threshold_days": 365,
                    "stale_handling": "downrank",
                },
            }

            def fake_load_json(path):
                if str(path).endswith("clauses.json"):
                    return {"clauses": clauses}
                return None

            query_module.load_json = fake_load_json
            query_module.load_yaml = lambda path: retrieval_config

            result = query_module.query(
                contract_family="nda",
                target_clauses=[{"clause_type": "confidentiality"}],
            )

            self.assertEqual(
                [candidate["doc_id"] for candidate in result["candidates"]["confidentiality"]],
                ["fresh-nda", "stale-nda"],
            )
            self.assertEqual(
                [candidate["freshness_rank"] for candidate in result["candidates"]["confidentiality"]],
                [0, 1],
            )
        finally:
            query_module.load_json = original_load_json
            query_module.load_yaml = original_load_yaml


class SessionEAudit013ParserTests(unittest.TestCase):
    def test_detect_format_rejects_legacy_doc_with_conversion_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_doc = Path(tmpdir) / "legacy.doc"
            legacy_doc.write_bytes(b"\xd0\xcf\x11\xe0")

            result = detect_format_module.detect_format(str(legacy_doc))

            self.assertFalse(result["supported"])
            self.assertIn(".doc", result["error"])
            self.assertIn(".docx", result["error"])
            self.assertIn("convert", result["error"])

    def test_normalize_flags_image_only_pdf_as_needing_ocr(self):
        original_extract_pdf_text = normalize_module.extract_pdf_text
        original_analyze_pdf = normalize_module.analyze_pdf

        try:
            normalize_module.extract_pdf_text = lambda path: None
            normalize_module.analyze_pdf = lambda path: {
                "page_count": 1,
                "has_extractable_text": False,
                "likely_image_only": True,
                "analysis_engine": "test",
            }

            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = Path(tmpdir) / "scan.pdf"
                pdf_path.write_bytes(b"%PDF-1.4\n% mock scan\n")
                output_dir = Path(tmpdir) / "normalized"

                result = normalize_module.normalize(str(pdf_path), str(output_dir))

                self.assertFalse(result["success"])
                self.assertTrue(result["needs_ocr"])
                self.assertEqual(result["pdf_analysis"]["analysis_engine"], "test")
                self.assertIn("OCR", result["error"])
        finally:
            normalize_module.extract_pdf_text = original_extract_pdf_text
            normalize_module.analyze_pdf = original_analyze_pdf


class SessionEAudit015CoverageTests(unittest.TestCase):
    def test_build_coverage_report_summarizes_family_and_unmapped_gaps(self):
        family_policy = {
            "families": [
                {"id": "nda"},
                {"id": "license"},
                {"id": "employment"},
            ]
        }
        clause_taxonomy = {
            "categories": [
                {
                    "id": "ip_confidentiality",
                    "clause_types": [
                        {"id": "confidentiality"},
                        {"id": "license_scope"},
                    ],
                }
            ]
        }
        documents_index = {"documents": [{"contract_family": "nda"}]}
        clauses_index = {
            "clauses": [
                {"contract_family": "nda", "clause_type": "confidentiality"},
                {"contract_family": "nda", "clause_type": "unmapped"},
                {"contract_family": "license", "clause_type": "license_scope"},
            ]
        }

        report = coverage_module.build_coverage_report(
            family_policy,
            clause_taxonomy,
            documents_index,
            clauses_index,
        )

        self.assertTrue(report["success"])
        self.assertEqual(report["configured_family_count"], 3)
        self.assertEqual(report["covered_family_count"], 2)
        self.assertEqual(report["uncovered_families"], ["employment"])
        self.assertEqual(report["total_unmapped_clause_count"], 1)
        self.assertAlmostEqual(report["total_unmapped_ratio"], 0.3333, places=4)
        self.assertEqual(report["unknown_clause_types"], [])

        nda_row = next(row for row in report["per_family"] if row["contract_family"] == "nda")
        self.assertEqual(nda_row["document_count"], 1)
        self.assertEqual(nda_row["clause_count"], 2)
        self.assertEqual(nda_row["unmapped_clause_count"], 1)
        self.assertAlmostEqual(nda_row["unmapped_ratio"], 0.5, places=4)


class SessionEAudit010AndDocsTests(unittest.TestCase):
    def test_wf5_docs_reference_compile_draft_js(self):
        drafting_agent = (REPO_ROOT / ".claude/agents/drafting-agent/AGENT.md").read_text(encoding="utf-8")
        draft_command = (REPO_ROOT / ".claude/commands/draft.md").read_text(encoding="utf-8")

        self.assertIn("compile-draft.js", drafting_agent)
        self.assertIn("compile-draft.js", draft_command)
        self.assertTrue(
            (REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-draft.js").exists(),
            "compile-draft.js script must exist",
        )

    def test_documented_family_count_matches_policy_yaml(self):
        family_policy = yaml.safe_load(
            (REPO_ROOT / "contract-review/library/policies/contract-families.yaml").read_text(encoding="utf-8")
        )
        family_count = len(family_policy["families"])

        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        how_to_use = (REPO_ROOT / "docs/en/HOW-TO-USE.md").read_text(encoding="utf-8")

        self.assertIn(f"{family_count} contract families", readme)
        self.assertIn(f"{family_count} contract families", how_to_use)


if __name__ == "__main__":
    unittest.main()

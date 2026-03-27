import importlib.util
import json
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


batch_module = load_module("batch_classify_and_publish", "scripts/batch_classify_and_publish.py")
query_module = load_module("query_index", ".claude/skills/index-manager/scripts/query-index.py")
validate_package_module = load_module(
    "validate_package",
    ".claude/skills/metadata-validator/scripts/validate-package.py",
)


class SessionAFixesTests(unittest.TestCase):
    def test_validate_package_accepts_list_outline_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir)
            (package_dir / "normalized").mkdir()
            (package_dir / "structure").mkdir()
            (package_dir / "clauses").mkdir()
            (package_dir / "quality").mkdir()

            (package_dir / "normalized" / "clean.md").write_text(
                "# Sample\n\nContract text.\n",
                encoding="utf-8",
            )
            (package_dir / "normalized" / "plain.txt").write_text(
                "Contract text.\n",
                encoding="utf-8",
            )

            outline = [
                {"line": 1, "level": 1, "text": "제1장"},
                {"line": 2, "level": 2, "text": "제1조"},
                {"line": 3, "level": 2, "text": "제2조"},
                {"line": 4, "level": 2, "text": "제3조"},
                {"line": 5, "level": 2, "text": "제4조"},
            ]
            (package_dir / "structure" / "outline.json").write_text(
                json.dumps(outline, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (package_dir / "structure" / "defined_terms.json").write_text(
                json.dumps([{"term": "계약", "first_line": 1}], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            manifest = {
                "doc_id": "sample-doc",
                "title": "Sample Contract",
                "doc_class": "template",
                "contract_family": "ssa",
                "paper_role": "neutral",
                "approval_state": "approved",
                "status": "active",
                "sha256": "a" * 64,
                "source_file": "sample.docx",
                "created_at": "2026-03-27T00:00:00+00:00",
                "governing_law": "대한민국 법률 (Korean law)",
                "jurisdiction": "KR",
                "freshness_sensitive": False,
            }
            (package_dir / "manifest.yaml").write_text(
                yaml.dump(manifest, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            for idx in range(1, 6):
                clause = {
                    "clause_id": f"clause-{idx:03d}",
                    "section_no": f"제{idx}조",
                    "heading": f"조항 {idx}",
                    "clause_type": "definitions" if idx == 1 else "purchase_price",
                    "text": f"(조항 {idx}) 본 계약의 조항 {idx} 본문",
                    "defined_terms_used": ["계약"],
                    "cross_refs": [],
                    "paragraph_count": 1,
                }
                (package_dir / "clauses" / f"clause-{idx:03d}.json").write_text(
                    json.dumps(clause, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            result = validate_package_module.validate_package(str(package_dir))

            self.assertTrue(result["valid"], result)
            self.assertEqual(result["stats"]["section_count"], 5)
            self.assertEqual(result["stats"]["invalid_clause_files"], 0)

    def test_segment_clauses_emits_rich_clause_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "clean.md"
            md_path.write_text(
                "\n".join(
                    [
                        "제1장 총칙",
                        "",
                        "(정의)",
                        "본 계약(이하 “계약”)은 당사자 사이에 체결된다.",
                        "",
                        "(준거법)",
                        "본 계약은 제1조 및 별지 1에 따른다.",
                    ]
                ),
                encoding="utf-8",
            )

            structure = batch_module.parse_structure(md_path)
            clauses = batch_module.segment_clauses(md_path, structure)

            self.assertGreaterEqual(len(structure["defined_terms"]), 1)
            self.assertEqual(clauses[1]["section_no"], "제1조")
            self.assertEqual(clauses[1]["heading"], "정의")
            self.assertIn("계약", clauses[1]["defined_terms_used"])
            self.assertIn("제1조", clauses[2]["cross_refs"])
            self.assertIn("별지 1", clauses[2]["cross_refs"])
            self.assertTrue(clauses[1]["text"].startswith("(정의)"))

    def test_query_enters_general_review_mode_when_no_usable_candidates(self):
        original_load_json = query_module.load_json
        original_load_yaml = query_module.load_yaml

        try:
            def fake_load_json(path):
                if str(path).endswith("clauses.json"):
                    return {
                        "clauses": [
                            {
                                "doc_id": "approved-nda",
                                "clause_id": "clause-001",
                                "contract_family": "nda",
                                "clause_type": "confidentiality",
                                "approval_state": "approved",
                                "status": "active",
                                "text": "Confidentiality clause",
                            }
                        ]
                    }
                return None

            query_module.load_json = fake_load_json
            query_module.load_yaml = lambda path: {}

            result = query_module.query(
                contract_family="ssa",
                target_clauses=[{"clause_type": "purchase_price"}],
            )

            self.assertFalse(result["library_empty"])
            self.assertTrue(result["general_review_mode"])
            self.assertEqual(result["fallback_reason"], "no_usable_candidates")
            self.assertEqual(result["total_candidates"], 0)
        finally:
            query_module.load_json = original_load_json
            query_module.load_yaml = original_load_yaml

    def test_query_treats_schema_drift_index_as_empty_library(self):
        original_load_json = query_module.load_json
        original_load_yaml = query_module.load_yaml

        try:
            def fake_load_json(path):
                if str(path).endswith("clauses.json"):
                    return {
                        "clauses": [
                            {
                                "doc_id": "legacy-row",
                                "clause_id": "clause-001",
                                "contract_family": "ssa",
                                "clause_type": "purchase_price",
                            }
                        ]
                    }
                return None

            query_module.load_json = fake_load_json
            query_module.load_yaml = lambda path: {}

            result = query_module.query(
                contract_family="ssa",
                target_clauses=[{"clause_type": "purchase_price"}],
            )

            self.assertTrue(result["library_empty"])
            self.assertTrue(result["general_review_mode"])
            self.assertEqual(result["fallback_reason"], "no_active_approved_library_records")
        finally:
            query_module.load_json = original_load_json
            query_module.load_yaml = original_load_yaml


if __name__ == "__main__":
    unittest.main()

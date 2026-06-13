import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers.docx_fixtures import write_minimal_docx


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mapping_module = load_module(
    "map_clauses_to_docx",
    ".claude/skills/docx-redliner/scripts/map-clauses-to-docx.py",
)


def write_clause(path: Path, clause_id: str, text: str) -> None:
    path.write_text(
        json.dumps(
            {
                "clause_id": clause_id,
                "heading": clause_id,
                "text": text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class DocxClauseMappingReliabilityTests(unittest.TestCase):
    def test_exact_multi_paragraph_clause_maps_to_span(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            clauses_dir = root / "clauses"
            clauses_dir.mkdir()
            write_clause(
                clauses_dir / "clause-001.json",
                "clause-001",
                "Seller shall notify Buyer. Payment is due within 30 days.",
            )
            docx_path = root / "contract.docx"
            write_minimal_docx(
                docx_path,
                ["Seller shall notify Buyer.", "Payment is due within 30 days."],
            )
            output_path = root / "docx-clause-map.json"

            result = mapping_module.map_clauses(str(clauses_dir), str(docx_path), str(output_path))
            saved = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertTrue(result["success"], result)
            self.assertEqual(result["coverage_status"], "proceed")
            self.assertEqual(saved["mappings"][0]["paragraph_indices"], [0, 1])
            self.assertEqual(saved["mappings"][0]["match_method"], "normalized_exact_span")
            self.assertGreaterEqual(saved["mappings"][0]["confidence"], 0.99)

    def test_low_similarity_clause_is_not_auto_mapped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            clauses_dir = root / "clauses"
            clauses_dir.mkdir()
            write_clause(
                clauses_dir / "clause-001.json",
                "clause-001",
                "This indemnity clause has bespoke uncapped liability language.",
            )
            docx_path = root / "contract.docx"
            write_minimal_docx(docx_path, ["Governing law is the law of Korea."])
            output_path = root / "docx-clause-map.json"

            result = mapping_module.map_clauses(str(clauses_dir), str(docx_path), str(output_path))
            saved = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertTrue(result["success"], result)
            self.assertEqual(result["coverage_status"], "halt")
            self.assertEqual(result["coverage"], 0)
            self.assertEqual(saved["unmapped_clause_ids"], ["clause-001"])
            self.assertFalse(saved["mappings"][0]["mapped"])

    def test_partial_coverage_requires_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            clauses_dir = root / "clauses"
            clauses_dir.mkdir()
            write_clause(clauses_dir / "clause-001.json", "clause-001", "Mapped clause text.")
            write_clause(clauses_dir / "clause-002.json", "clause-002", "Unmapped bespoke clause.")
            docx_path = root / "contract.docx"
            write_minimal_docx(docx_path, ["Mapped clause text."])
            output_path = root / "docx-clause-map.json"

            result = mapping_module.map_clauses(str(clauses_dir), str(docx_path), str(output_path))

            self.assertTrue(result["success"], result)
            self.assertEqual(result["coverage"], 0.5)
            self.assertEqual(result["coverage_status"], "partial")
            self.assertTrue(result["fallback_required"])
            self.assertFalse(result["halt_required"])
            self.assertEqual(result["unmapped_clause_ids"], ["clause-002"])


if __name__ == "__main__":
    unittest.main()

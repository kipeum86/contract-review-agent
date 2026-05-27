import importlib.util
import subprocess
import tempfile
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


query_module = load_module(
    "query_index_generated_index_handling",
    ".claude/skills/index-manager/scripts/query-index.py",
)


class GeneratedIndexHandlingTests(unittest.TestCase):
    def test_query_missing_indexes_enters_general_review_with_rebuild_hint(self):
        original_indexes_dir = query_module.INDEXES_DIR

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                query_module.INDEXES_DIR = str(Path(tmpdir) / "missing-indexes")

                result = query_module.query(
                    contract_family="nda",
                    target_clauses=[{"clause_type": "confidentiality"}],
                )

            self.assertTrue(result["success"])
            self.assertTrue(result["index_missing"])
            self.assertTrue(result["library_empty"])
            self.assertTrue(result["general_review_mode"])
            self.assertEqual(result["fallback_reason"], "library_empty")
            self.assertEqual(result["total_candidates"], 0)
            self.assertIn("Rebuild local indexes", result["message"])
        finally:
            query_module.INDEXES_DIR = original_indexes_dir

    def test_search_missing_indexes_returns_empty_results_with_rebuild_hint(self):
        original_indexes_dir = query_module.INDEXES_DIR

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                query_module.INDEXES_DIR = str(Path(tmpdir) / "missing-indexes")

                result = query_module.search(query_text="liability")

            self.assertTrue(result["success"])
            self.assertTrue(result["index_missing"])
            self.assertTrue(result["library_empty"])
            self.assertEqual(result["documents_found"], 0)
            self.assertEqual(result["clauses_found"], 0)
            self.assertEqual(result["results"], {"documents": [], "clauses": []})
            self.assertIn("Rebuild local indexes", result["message"])
        finally:
            query_module.INDEXES_DIR = original_indexes_dir

    def test_generated_index_jsons_are_gitignored(self):
        ignored_path = "contract-review/library/indexes/clause-texts.json"
        tracked_scaffold_path = "contract-review/library/indexes/README.md"

        ignored = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", ignored_path],
            cwd=REPO_ROOT,
            check=False,
        )
        scaffold = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", tracked_scaffold_path],
            cwd=REPO_ROOT,
            check=False,
        )

        self.assertEqual(ignored.returncode, 0)
        self.assertNotEqual(scaffold.returncode, 0)

    def test_planning_notes_are_local_only_except_readme(self):
        plan_path = "docs/plans/example-implementation-plan.md"
        readme_path = "docs/plans/README.md"

        ignored = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", plan_path],
            cwd=REPO_ROOT,
            check=False,
        )
        readme = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", readme_path],
            cwd=REPO_ROOT,
            check=False,
        )

        self.assertEqual(ignored.returncode, 0)
        self.assertNotEqual(readme.returncode, 0)

    def test_public_seed_allowlist_uses_generic_pattern(self):
        seed_path = (
            "contract-review/library/approved/templates/nda/"
            "0-nda-mutual-seed/manifest.yaml"
        )
        local_asset_path = (
            "contract-review/library/approved/templates/ssa/"
            "standard-investment-agreement/manifest.yaml"
        )

        seed = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", seed_path],
            cwd=REPO_ROOT,
            check=False,
        )
        local_asset = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", local_asset_path],
            cwd=REPO_ROOT,
            check=False,
        )

        self.assertNotEqual(seed.returncode, 0)
        self.assertEqual(local_asset.returncode, 0)


if __name__ == "__main__":
    unittest.main()

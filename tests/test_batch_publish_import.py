"""Audit C-1: importing batch_classify_and_publish must not require local run files."""
import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class BatchPublishImportTests(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.spec_from_file_location(
            "batch_classify_and_publish_import_test",
            str(REPO_ROOT / "scripts" / "batch_classify_and_publish.py"),
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_import_succeeds_without_local_run_artifacts(self):
        # Must not raise IndexError even when runs/ingestion/ is empty.
        module = self.load_module()
        self.assertTrue(hasattr(module, "latest_summary_file"))

    def test_latest_summary_file_gives_clear_error_when_empty(self):
        module = self.load_module()
        empty = REPO_ROOT / "contract-review" / "library" / "runs" / "ingestion"
        has_summaries = any(empty.glob("*_batch-summary.json"))
        if has_summaries:
            self.skipTest("local run artifacts present; empty-state path not testable here")
        with self.assertRaises(SystemExit) as ctx:
            module.latest_summary_file()
        self.assertIn("batch-summary", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

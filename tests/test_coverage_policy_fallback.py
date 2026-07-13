"""Audit D-2: coverage report must fall back to policies.default when the
user policies dir is empty, instead of silently reporting zero coverage."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        module_name, str(REPO_ROOT / relative_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CoveragePolicyFallbackTests(unittest.TestCase):
    def test_empty_policies_dir_falls_back_to_defaults(self):
        coverage = load_module(
            "report_coverage_fallback_test",
            ".claude/skills/index-manager/scripts/report-coverage.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            coverage.POLICIES_DIR = tmp  # simulate uninitialized policies/
            report = coverage.generate_report()
        self.assertGreater(
            report["configured_family_count"], 0,
            "empty policies/ must fall back to policies.default/, not report 0 families",
        )


if __name__ == "__main__":
    unittest.main()

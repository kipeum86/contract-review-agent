"""Audit D-1: if the external-clean scanner crashes, the unscanned output
DOCX must be deleted — never left on disk looking deliverable."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.helpers.docx_fixtures import write_minimal_docx


def load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        module_name, str(REPO_ROOT / relative_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


strip_module = load_module(
    "strip_internal_comments_failsafe_test",
    ".claude/skills/docx-redliner/scripts/strip-internal-comments.py",
)


class StripScanFailsafeTests(unittest.TestCase):
    def test_scanner_crash_deletes_output_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.docx"
            output = Path(tmp) / "out_clean.docx"
            write_minimal_docx(source, ["Hello world"])

            crashing_scanner = mock.Mock()
            crashing_scanner.scan_docx.side_effect = RuntimeError("policy missing")

            with mock.patch.object(
                strip_module, "load_external_clean_scanner",
                return_value=crashing_scanner,
            ):
                result = strip_module.strip_internal_comments(str(source), str(output))

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "external_clean_scan_crashed")
            self.assertFalse(
                output.exists(),
                "unscanned _clean.docx must not remain on disk after scanner crash",
            )


if __name__ == "__main__":
    unittest.main()

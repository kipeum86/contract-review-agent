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
from tests.helpers.docx_fixtures import write_zip_package, zip_members


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


LOWERCASE_INTERNAL_DOCX = {
    "[Content_Types].xml": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
        "</Types>"
    ),
    "_rels/.rels": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    ),
    "word/_rels/document.xml.rels": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>'
        "</Relationships>"
    ),
    "word/document.xml": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Clause text</w:t></w:r></w:p></w:body></w:document>"
    ),
    "word/comments.xml": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:comment w:id="1" w:author="R">'
        "<w:p><w:r><w:t>[internal] lowercase strategy note with fallback plan</w:t></w:r></w:p>"
        "</w:comment></w:comments>"
    ),
}


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


class StripCaseInsensitivityTests(unittest.TestCase):
    def test_lowercase_internal_prefix_is_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.docx"
            output = Path(tmp) / "out_clean.docx"
            write_zip_package(source, LOWERCASE_INTERNAL_DOCX)

            result = strip_module.strip_internal_comments(str(source), str(output))

            self.assertTrue(result["success"], result)
            self.assertEqual(result["internal_comments_stripped"], 1)
            self.assertNotIn("word/comments.xml", zip_members(output))


if __name__ == "__main__":
    unittest.main()

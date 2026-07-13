"""External-clean policy must block Korean strategy terms and process markers.

Audit findings B-1 / B-2: the final DOCX scan gate previously contained only
English patterns, so Korean internal-strategy text (and the [MANUAL_REQUIRED]
placeholder) could survive into the counterparty deliverable.
"""
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


scanner = load_module(
    "scan_docx_for_internal_markers",
    ".claude/skills/docx-redliner/scripts/scan-docx-for-internal-markers.py",
)

COMMENTS_XML_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:comments xmlns:w='
    '"http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:comment w:id="1" w:author="R">'
    "<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
    "</w:comment></w:comments>"
)

CORE_PROPS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<cp:coreProperties'
    ' xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    "<dc:title>[INTERNAL] negotiation strategy v3</dc:title>"
    "</cp:coreProperties>"
)


class ExternalCleanPolicyKoreanTests(unittest.TestCase):
    def scan_comment_text(self, text: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            word_dir = Path(tmp) / "word"
            word_dir.mkdir(parents=True)
            (word_dir / "comments.xml").write_text(
                COMMENTS_XML_TEMPLATE.format(text=text), encoding="utf-8"
            )
            return scanner.scan_unpacked_docx(tmp)

    def assert_blocked(self, text: str, expected_pattern_id: str):
        result = self.scan_comment_text(text)
        self.assertEqual(result["status"], "fail", f"expected block for: {text}")
        matched_ids = {v["pattern_id"] for v in result["violations"]}
        self.assertIn(expected_pattern_id, matched_ids)

    def test_korean_bottom_line_blocked(self):
        self.assert_blocked("우리 측 마지노선은 3개월입니다.", "bottom_line_ko")

    def test_korean_negotiation_strategy_blocked(self):
        self.assert_blocked("협상 전략상 이 조항은 후순위로 미룬다.", "negotiation_strategy_ko")

    def test_korean_acceptance_threshold_blocked(self):
        self.assert_blocked("6개월까지는 수용 가능합니다.", "acceptance_threshold_ko")

    def test_korean_concession_blocked(self):
        self.assert_blocked("이 항목은 양보 가능한 카드입니다.", "concession_ko")

    def test_korean_internal_marker_blocked(self):
        self.assert_blocked("[내부] 검토 메모입니다.", "internal_marker_ko")

    def test_manual_required_placeholder_blocked(self):
        self.assert_blocked(
            "[MANUAL_REQUIRED] Audience firewall could not be satisfied. "
            "Manual drafting required.",
            "manual_required_marker",
        )

    def test_legitimate_korean_contract_text_passes(self):
        result = self.scan_comment_text(
            "본 조의 통지 기간은 30일로 하며, 양 당사자는 서면으로 통지한다."
        )
        self.assertEqual(result["status"], "pass", result.get("violations"))

    def test_existing_english_patterns_still_blocked(self):
        self.assert_blocked("[INTERNAL] fallback ladder here", "internal_marker")


class ScannerPartCoverageTests(unittest.TestCase):
    def test_docprops_core_is_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            docprops = Path(tmp) / "docProps"
            docprops.mkdir(parents=True)
            (docprops / "core.xml").write_text(CORE_PROPS_XML, encoding="utf-8")
            result = scanner.scan_unpacked_docx(tmp)
        self.assertEqual(result["status"], "fail", result)
        self.assertIn(
            "docProps/core.xml", {v["part"] for v in result["violations"]}
        )


if __name__ == "__main__":
    unittest.main()

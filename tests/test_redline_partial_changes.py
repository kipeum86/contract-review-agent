"""
Tests for the partial tracked-change (redline) algorithm in apply-redlines.py.

Covers:
  A. Unit tests for diff boundary functions
  B. Integration tests for partial redline application
  C. Edge-case tests
"""

import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = load_module(
    "apply_redlines",
    ".claude/skills/docx-redliner/scripts/apply-redlines.py",
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def direct_paragraphs(document_path: Path):
    tree = ET.parse(document_path)
    root = tree.getroot()
    body = root.find(f".//{{{W_NS}}}body")
    assert body is not None
    return body.findall(f"{{{W_NS}}}p")


def para_xml(document_path: Path, index: int) -> str:
    paragraphs = direct_paragraphs(document_path)
    return ET.tostring(paragraphs[index], encoding="unicode")


def make_document_xml(paragraphs: list[str]) -> str:
    """Build a minimal document.xml from a list of paragraph texts."""
    para_elems = []
    for text in paragraphs:
        para_elems.append(
            f'    <w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
        )
    body = "\n".join(para_elems)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        "  <w:body>\n"
        f"{body}\n"
        "  </w:body>\n"
        "</w:document>\n"
    )


def run_redline(tmpdir, paragraphs: list[str], clause_map: dict, redlines: dict) -> dict:
    """Set up files and run apply_redlines, return result dict."""
    doc_path = Path(tmpdir) / "document.xml"
    write_file(doc_path, make_document_xml(paragraphs))

    map_path = Path(tmpdir) / "clause-map.json"
    map_path.write_text(json.dumps(clause_map, ensure_ascii=False), encoding="utf-8")

    red_path = Path(tmpdir) / "redlines.json"
    red_path.write_text(json.dumps(redlines, ensure_ascii=False), encoding="utf-8")

    out_path = Path(tmpdir) / "output.xml"
    result = mod.apply_redlines(str(doc_path), str(map_path), str(red_path), str(out_path))
    result["_out"] = out_path
    return result


# ──────────────────────────────────────────────
# A. Unit tests — diff boundary functions
# ──────────────────────────────────────────────

class TestCommonPrefixLength(unittest.TestCase):
    def test_identical_strings(self):
        self.assertEqual(mod.common_prefix_length("hello", "hello"), 5)

    def test_no_common_prefix(self):
        self.assertEqual(mod.common_prefix_length("abc", "xyz"), 0)

    def test_partial_prefix(self):
        self.assertEqual(mod.common_prefix_length("abcdef", "abcxyz"), 3)

    def test_empty_left(self):
        self.assertEqual(mod.common_prefix_length("", "hello"), 0)

    def test_empty_right(self):
        self.assertEqual(mod.common_prefix_length("hello", ""), 0)

    def test_both_empty(self):
        self.assertEqual(mod.common_prefix_length("", ""), 0)

    def test_korean_strings(self):
        # "매도인은 " = 5 chars (4 hangul + space)
        self.assertEqual(mod.common_prefix_length("매도인은 30일 이내에", "매도인은 10일 이내에"), 5)

    def test_one_is_prefix_of_other(self):
        self.assertEqual(mod.common_prefix_length("abc", "abcdef"), 3)


class TestCommonSuffixLength(unittest.TestCase):
    def test_identical_strings(self):
        self.assertEqual(mod.common_suffix_length("hello", "hello", 5), 0)

    def test_shared_suffix(self):
        # "30 days." vs "10 days." — suffix "0 days." = 7 chars (the '0' also matches)
        self.assertEqual(mod.common_suffix_length("30 days.", "10 days.", 0), 7)

    def test_no_suffix(self):
        self.assertEqual(mod.common_suffix_length("abc", "xyz", 0), 0)

    def test_prefix_excluded(self):
        # "Seller pays within 30 days." vs "Seller pays within 10 days."
        # prefix = 19 ("Seller pays within "), suffix = 7 ("0 days." — '0' matches too)
        left = "Seller pays within 30 days."
        right = "Seller pays within 10 days."
        prefix = mod.common_prefix_length(left, right)  # 19
        suffix = mod.common_suffix_length(left, right, prefix)
        self.assertEqual(suffix, 7)

    def test_full_overlap_minus_prefix(self):
        self.assertEqual(mod.common_suffix_length("abc", "xbc", 0), 2)

    def test_korean_suffix(self):
        left = "매도인은 30일 이내에 지급한다."
        right = "매도인은 10일 이내에 지급한다."
        prefix = mod.common_prefix_length(left, right)
        suffix = mod.common_suffix_length(left, right, prefix)
        self.assertGreater(suffix, 0)


class TestIsTokenChar(unittest.TestCase):
    def test_alpha(self):
        self.assertTrue(mod.is_token_char("a"))
        self.assertTrue(mod.is_token_char("Z"))

    def test_digit(self):
        self.assertTrue(mod.is_token_char("5"))

    def test_underscore(self):
        self.assertTrue(mod.is_token_char("_"))

    def test_korean(self):
        self.assertTrue(mod.is_token_char("가"))

    def test_space(self):
        self.assertFalse(mod.is_token_char(" "))

    def test_punctuation(self):
        self.assertFalse(mod.is_token_char("."))
        self.assertFalse(mod.is_token_char(","))


class TestAdjustDiffBoundaries(unittest.TestCase):
    def test_no_adjustment_at_word_boundary(self):
        # "pay X days" vs "pay Y days"
        # prefix=4 ("pay "), suffix=5 (" days")
        # suffix boundary: left[5]=' '(prev) is NOT token char → no split → no adjustment
        left = "pay X days"
        right = "pay Y days"
        prefix = mod.common_prefix_length(left, right)
        suffix = mod.common_suffix_length(left, right, prefix)
        adj_prefix, adj_suffix = mod.adjust_diff_boundaries(left, right, prefix, suffix)
        self.assertEqual(adj_prefix, prefix)
        self.assertEqual(adj_suffix, suffix)

    def test_adjustment_when_splitting_token(self):
        # "pay 30 days" vs "pay 10 days"
        # prefix=4 ("pay "), suffix=6 ("0 days" — '0' also matches)
        # suffix boundary: left[5-1]='3' (token) and left[5]='0' (token) → split mid-token "30"
        # adjust should reduce suffix from 6 to 5, separating "0" from suffix
        left = "pay 30 days"
        right = "pay 10 days"
        prefix = mod.common_prefix_length(left, right)
        suffix = mod.common_suffix_length(left, right, prefix)
        self.assertEqual(suffix, 6)  # naive: "0 days" matches
        adj_prefix, adj_suffix = mod.adjust_diff_boundaries(left, right, prefix, suffix)
        self.assertEqual(adj_suffix, 5)  # adjusted: " days" only, "30"/"10" kept whole

    def test_zero_suffix_unchanged(self):
        prefix_len, suffix_len = mod.adjust_diff_boundaries("abc", "xyz", 0, 0)
        self.assertEqual(suffix_len, 0)

    def test_korean_token_boundary(self):
        # "계약금액 100만원" vs "계약금액 200만원" — space separates tokens
        # prefix=5 ("계약금액 "), suffix: "00만원"=4 chars match
        # suffix boundary: left[8-1]='1'(token), left[8]='0'(token) → mid-token split
        # should adjust suffix down
        left = "계약금액 100만원"
        right = "계약금액 200만원"
        prefix = mod.common_prefix_length(left, right)
        suffix = mod.common_suffix_length(left, right, prefix)
        adj_prefix, adj_suffix = mod.adjust_diff_boundaries(left, right, prefix, suffix)
        # "만원" boundary: '0'(token) and '만'(token) → keeps adjusting
        # Eventually suffix should be reduced so numbers stay whole
        self.assertLessEqual(adj_suffix, suffix)


# ──────────────────────────────────────────────
# B. Integration tests — partial redline application
# ──────────────────────────────────────────────

class TestPartialRedlineIntegration(unittest.TestCase):

    def test_single_word_change(self):
        """'30 days' → '10 days' — only the number should be tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Seller shall pay within 30 days."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "Seller shall pay within 10 days."}},
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["applied_count"], 1)
            self.assertEqual(result["paragraphs_touched"], 1)

            xml = para_xml(result["_out"], 0)
            # Prefix preserved as plain run
            self.assertIn("Seller shall pay within ", xml)
            # Deletion of old
            self.assertIn("<w:delText", xml)
            self.assertIn(">30<", xml)
            # Insertion of new
            self.assertIn("<w:ins", xml)
            self.assertIn(">10<", xml)
            # Suffix preserved as plain run
            self.assertIn("> days.<", xml)

    def test_beginning_change(self):
        """'Seller shall ...' → 'Buyer shall ...' — front change only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Seller shall deliver the goods."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "Buyer shall deliver the goods."}},
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["paragraphs_touched"], 1)

            xml = para_xml(result["_out"], 0)
            self.assertIn("<w:delText", xml)
            self.assertIn("<w:ins", xml)
            # Suffix should be preserved
            self.assertIn(" shall deliver the goods.", xml)

    def test_end_change(self):
        """'...within 30 days' → '...within 60 business days'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Payment is due within 30 days."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "Payment is due within 60 business days."}},
            )
            self.assertTrue(result["success"])
            xml = para_xml(result["_out"], 0)
            self.assertIn("Payment is due within ", xml)
            self.assertIn("<w:delText", xml)
            self.assertIn("<w:ins", xml)

    def test_full_replacement(self):
        """Completely different text — entire paragraph should be tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["The old clause text goes here."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "A completely new and different provision."}},
            )
            self.assertTrue(result["success"])
            xml = para_xml(result["_out"], 0)
            self.assertIn("<w:delText", xml)
            self.assertIn("<w:ins", xml)

    def test_insertion_only(self):
        """Original + appended text — only the new portion should be ins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Seller shall notify Buyer."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "Seller shall notify Buyer in writing."}},
            )
            self.assertTrue(result["success"])
            xml = para_xml(result["_out"], 0)
            # Original prefix preserved
            self.assertIn("Seller shall notify Buyer", xml)
            # Insertion present (at minimum " in writing" is inserted)
            self.assertIn("<w:ins", xml)
            # Suffix "." is shared, so the change is between "Buyer" and "."
            # del: nothing (empty middle on old side) or ins: " in writing"
            self.assertIn("in writing", xml)

    def test_deletion_only(self):
        """Shortened text — removed portion should be del."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Seller shall promptly notify Buyer."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "Seller shall notify Buyer."}},
            )
            self.assertTrue(result["success"])
            xml = para_xml(result["_out"], 0)
            self.assertIn("<w:delText", xml)
            self.assertIn("promptly ", xml)

    def test_korean_redline(self):
        """Korean clause: '매도인은' → '매수인은'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["매도인은 대금을 30일 이내에 지급한다."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "매수인은 대금을 30일 이내에 지급한다."}},
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["paragraphs_touched"], 1)
            xml = para_xml(result["_out"], 0)
            self.assertIn("<w:delText", xml)
            self.assertIn("<w:ins", xml)
            # Suffix preserved
            self.assertIn("대금을 30일 이내에 지급한다.", xml)

    def test_multi_paragraph_redline(self):
        """Two paragraphs mapped to one clause, both changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Seller shall notify Buyer.", "Payment is due within 30 days."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0, 1]}]},
                {"c1": {"suggested_redline": "Seller shall promptly notify Buyer.\n\nPayment is due within 10 days."}},
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["applied_count"], 1)
            self.assertEqual(result["paragraphs_touched"], 2)

            xml0 = para_xml(result["_out"], 0)
            xml1 = para_xml(result["_out"], 1)
            self.assertIn("promptly", xml0)
            self.assertIn(">10<", xml1)

    def test_existing_tracked_changes_preserved(self):
        """Redline on paragraph 1 must not destroy existing w:ins on paragraph 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = Path(tmpdir) / "document.xml"
            write_file(
                doc_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:ins w:id="5" w:author="Prior" w:date="2026-01-01T00:00:00Z">
        <w:r><w:t>Existing insertion</w:t></w:r>
      </w:ins>
    </w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Seller pays 30 days.</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
""",
            )
            map_path = Path(tmpdir) / "clause-map.json"
            map_path.write_text(
                json.dumps({"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [1]}]}),
                encoding="utf-8",
            )
            red_path = Path(tmpdir) / "redlines.json"
            red_path.write_text(
                json.dumps({"c1": {"suggested_redline": "Seller pays 10 days."}}),
                encoding="utf-8",
            )
            out_path = Path(tmpdir) / "output.xml"
            result = mod.apply_redlines(str(doc_path), str(map_path), str(red_path), str(out_path))

            self.assertTrue(result["success"])
            paragraphs = direct_paragraphs(out_path)
            # Paragraph 0: existing insertion still present
            p0_xml = ET.tostring(paragraphs[0], encoding="unicode")
            self.assertIn('w:author="Prior"', p0_xml)
            self.assertIn("Existing insertion", p0_xml)
            # Paragraph 1: new redline applied
            p1_xml = ET.tostring(paragraphs[1], encoding="unicode")
            self.assertIn("<w:delText", p1_xml)
            self.assertIn(">30<", p1_xml)
            self.assertIn(">10<", p1_xml)


# ──────────────────────────────────────────────
# C. Edge-case tests
# ──────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_empty_paragraph(self):
        """Redlining an empty paragraph should insert the new text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = Path(tmpdir) / "document.xml"
            write_file(
                doc_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p></w:p>
  </w:body>
</w:document>
""",
            )
            map_path = Path(tmpdir) / "clause-map.json"
            map_path.write_text(
                json.dumps({"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]}),
                encoding="utf-8",
            )
            red_path = Path(tmpdir) / "redlines.json"
            red_path.write_text(
                json.dumps({"c1": {"suggested_redline": "New content here."}}),
                encoding="utf-8",
            )
            out_path = Path(tmpdir) / "output.xml"
            result = mod.apply_redlines(str(doc_path), str(map_path), str(red_path), str(out_path))

            self.assertTrue(result["success"])
            self.assertEqual(result["paragraphs_touched"], 1)
            xml = ET.tostring(direct_paragraphs(out_path)[0], encoding="unicode")
            self.assertIn("<w:ins", xml)
            self.assertIn("New content here.", xml)

    def test_no_run_paragraph(self):
        """Paragraph with pPr but no runs — should still apply redline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = Path(tmpdir) / "document.xml"
            write_file(
                doc_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:jc w:val="center"/></w:pPr>
    </w:p>
  </w:body>
</w:document>
""",
            )
            map_path = Path(tmpdir) / "clause-map.json"
            map_path.write_text(
                json.dumps({"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]}),
                encoding="utf-8",
            )
            red_path = Path(tmpdir) / "redlines.json"
            red_path.write_text(
                json.dumps({"c1": {"suggested_redline": "Inserted text."}}),
                encoding="utf-8",
            )
            out_path = Path(tmpdir) / "output.xml"
            result = mod.apply_redlines(str(doc_path), str(map_path), str(red_path), str(out_path))

            self.assertTrue(result["success"])
            self.assertEqual(result["paragraphs_touched"], 1)
            xml = ET.tostring(direct_paragraphs(out_path)[0], encoding="unicode")
            self.assertIn("<w:ins", xml)
            # pPr should still be present
            self.assertIn("w:jc", xml)

    def test_identical_text_no_op(self):
        """Same text → no tracked change, paragraphs_touched = 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["This text does not change."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"suggested_redline": "This text does not change."}},
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["paragraphs_touched"], 0)
            self.assertEqual(result["applied_count"], 0)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(result["total_redlines"], 1)
            self.assertIn('No redlines were applied despite 1 redline entries', result["error"])

            xml = para_xml(result["_out"], 0)
            self.assertNotIn("<w:ins", xml)
            self.assertNotIn("<w:del", xml)

    def test_unmapped_clause_counted_as_failure(self):
        """Clause not in mapping → failed_count incremented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Some text."],
                {"mappings": []},
                {"c1": {"suggested_redline": "Changed text."}},
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["applied_count"], 0)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(result["total_redlines"], 1)

    def test_reviewer_metadata_from_meta(self):
        """Reviewer author/initials come from _meta block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Pay within 30 days."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {
                    "_meta": {"reviewer": {"author": "Contract Review Specialist", "initials": "CRS"}},
                    "c1": {"suggested_redline": "Pay within 10 days."},
                },
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["reviewer"]["author"], "Contract Review Specialist")
            self.assertEqual(result["reviewer"]["initials"], "CRS")

            xml = para_xml(result["_out"], 0)
            self.assertIn('w:author="Contract Review Specialist"', xml)

    def test_paragraph_index_out_of_range(self):
        """Mapping points to non-existent paragraph → graceful skip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Only one paragraph."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [5]}]},
                {"c1": {"suggested_redline": "Changed."}},
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["applied_count"], 0)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(result["total_redlines"], 1)

    def test_zero_redline_entries_returns_warning_but_success(self):
        """No redline entries is a legitimate no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Some text."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"_meta": {"reviewer_author": "Reviewer", "reviewer_initials": "RV"}},
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["applied_count"], 0)
            self.assertEqual(result["total_redlines"], 0)
            self.assertEqual(
                result["error"],
                "Input redlines.json contains zero entries (excluding _meta).",
            )

    def test_missing_suggested_redline_field_fails_loudly(self):
        """Schema mismatch should not masquerade as success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_redline(
                tmpdir,
                ["Some text."],
                {"mappings": [{"clause_id": "c1", "mapped": True, "paragraph_indices": [0]}]},
                {"c1": {"new_text": "Changed text."}},
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["applied_count"], 0)
            self.assertEqual(result["total_redlines"], 1)
            self.assertIn('"suggested_redline"', result["error"])


# ──────────────────────────────────────────────
# D. Unit tests — helper functions
# ──────────────────────────────────────────────

class TestHelperFunctions(unittest.TestCase):

    def test_split_redline_paragraphs_single(self):
        parts = mod.split_redline_paragraphs("Hello world.")
        self.assertEqual(parts, ["Hello world."])

    def test_split_redline_paragraphs_multi(self):
        parts = mod.split_redline_paragraphs("First paragraph.\n\nSecond paragraph.")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "First paragraph.")
        self.assertEqual(parts[1], "Second paragraph.")

    def test_split_redline_paragraphs_none(self):
        parts = mod.split_redline_paragraphs(None)
        self.assertEqual(parts, [])

    def test_split_redline_paragraphs_empty(self):
        parts = mod.split_redline_paragraphs("")
        self.assertEqual(parts, [""])

    def test_local_name_with_namespace(self):
        self.assertEqual(mod.local_name("{http://example.com}body"), "body")

    def test_local_name_without_namespace(self):
        self.assertEqual(mod.local_name("body"), "body")

    def test_make_revision_id_empty_document(self):
        root = ET.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body/></w:document>"
        )
        self.assertEqual(mod.make_revision_id(root), 1)

    def test_make_revision_id_existing_revisions(self):
        root = ET.fromstring(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p>"
            '<w:ins w:id="10" w:author="A" w:date="2026-01-01T00:00:00Z">'
            "<w:r><w:t>text</w:t></w:r></w:ins>"
            "</w:p></w:body></w:document>"
        )
        self.assertEqual(mod.make_revision_id(root), 11)


if __name__ == "__main__":
    unittest.main()

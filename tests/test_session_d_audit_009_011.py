import importlib.util
import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


apply_comments_module = load_module(
    "apply_comments",
    ".claude/skills/docx-redliner/scripts/apply-comments.py",
)
apply_redlines_module = load_module(
    "apply_redlines",
    ".claude/skills/docx-redliner/scripts/apply-redlines.py",
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_zip_text(docx_path: Path, member: str) -> str:
    with zipfile.ZipFile(docx_path, "r") as archive:
        return archive.read(member).decode("utf-8")


def direct_paragraphs(document_path: Path):
    tree = ET.parse(document_path)
    root = tree.getroot()
    body = root.find(f".//{{{W_NS}}}body")
    assert body is not None
    return body.findall(f"{{{W_NS}}}p")


def make_clause(index: int, *, include_action: bool = False, korean: bool = False) -> dict:
    prefix = "제" if korean else "§"
    clause = {
        "clause_id": f"clause-{index:03d}",
        "section_no": f"{prefix}{index}조" if korean else str(index),
        "heading": f"Clause {index}",
        "clause_type": "general_clause",
        "risk_level": "high" if index <= 5 else "medium",
        "risk_rationale": f"Clause {index} shifts risk to the client.",
        "divergence": f"Clause {index} diverges from the preferred baseline.",
        "playbook_tier": "fallback" if index <= 5 else "acceptable",
        "playbook_missing": False,
        "suggested_redline": f"Revised clause text {index}.",
        "internal_note": f"Internal note for clause {index}.",
    }
    if include_action:
        clause["suggested_action"] = f"Negotiate clause {index} back to the preferred position."
    return clause


class SessionDAudit009CommentsTests(unittest.TestCase):
    def test_apply_comments_preserves_existing_comments_and_package_parts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            unpacked_dir = Path(tmpdir) / "unpacked"
            write_file(
                unpacked_dir / "word" / "document.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:bookmarkStart w:id="0" w:name="_GoBack"/>
      <w:r><w:t>Clause text for comments.</w:t></w:r>
      <w:bookmarkEnd w:id="0"/>
    </w:p>
  </w:body>
</w:document>
""",
            )
            write_file(
                unpacked_dir / "word" / "comments.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="4" w:author="Existing Reviewer" w:initials="ER" w:date="2026-03-27T00:00:00Z">
    <w:p><w:r><w:t>Existing comment</w:t></w:r></w:p>
  </w:comment>
</w:comments>
""",
            )
            write_file(
                unpacked_dir / "word" / "_rels" / "document.xml.rels",
                """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
""",
            )
            write_file(
                unpacked_dir / "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
            )

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps(
                    {
                        "mappings": [
                            {"clause_id": "clause-001", "mapped": True, "paragraph_indices": [0]}
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            comments_path = Path(tmpdir) / "comments.json"
            comments_path.write_text(
                json.dumps(
                    {
                        "_meta": {
                            "reviewer_author": "Client Legal",
                            "reviewer_initials": "CL",
                        },
                        "clause-001": {
                            "external_comment": "Please clarify this obligation.",
                            "internal_note": "Fallback position is 10 business days.",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = apply_comments_module.apply_comments(
                str(unpacked_dir),
                str(clause_map_path),
                str(comments_path),
            )

            self.assertTrue(result["success"], result)
            self.assertEqual(result["total_comments"], 2)
            self.assertEqual(result["reviewer"]["author"], "Client Legal")
            self.assertTrue(result["comments_relationship_added"])
            self.assertTrue(result["comments_content_type_added"])

            comments_tree = ET.parse(unpacked_dir / "word" / "comments.xml")
            comments_root = comments_tree.getroot()
            comments = comments_root.findall(f"{{{W_NS}}}comment")
            comment_ids = [comment.get(f"{{{W_NS}}}id") for comment in comments]

            self.assertEqual(comment_ids, ["4", "5", "6"])
            self.assertEqual(comments[0].get(f"{{{W_NS}}}author"), "Existing Reviewer")
            self.assertEqual(comments[1].get(f"{{{W_NS}}}author"), "Client Legal")
            self.assertEqual(comments[2].get(f"{{{W_NS}}}author"), "Client Legal")

            document_tree = ET.parse(unpacked_dir / "word" / "document.xml")
            document_root = document_tree.getroot()
            paragraph = document_root.find(f".//{{{W_NS}}}p")
            self.assertIsNotNone(paragraph)
            child_local_names = [child.tag.split("}")[-1] for child in list(paragraph)]
            self.assertIn("bookmarkStart", child_local_names)
            self.assertIn("bookmarkEnd", child_local_names)
            self.assertIn("commentRangeStart", child_local_names)
            self.assertIn("commentRangeEnd", child_local_names)
            self.assertEqual(child_local_names.count("commentReference"), 0)
            self.assertEqual(child_local_names.count("r"), 3)

            rels_tree = ET.parse(unpacked_dir / "word" / "_rels" / "document.xml.rels")
            rels_root = rels_tree.getroot()
            relationship_types = [rel.get("Type") for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")]
            self.assertIn(
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
                relationship_types,
            )

            content_types_tree = ET.parse(unpacked_dir / "[Content_Types].xml")
            content_types_root = content_types_tree.getroot()
            overrides = [
                override.get("PartName")
                for override in content_types_root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
            ]
            self.assertIn("/word/comments.xml", overrides)

    def _write_minimal_docx_package(self, unpacked_dir: Path) -> None:
        """Helper: write a minimal DOCX package for comment tests."""
        write_file(
            unpacked_dir / "word" / "document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Clause text for comments.</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
""",
        )
        write_file(
            unpacked_dir / "word" / "comments.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
</w:comments>
""",
        )
        write_file(
            unpacked_dir / "word" / "_rels" / "document.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
""",
        )
        write_file(
            unpacked_dir / "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )

    def test_apply_comments_accepts_v2_list_schema(self):
        """v2 schema: each clause_id maps to a list of {audience, text} entries.

        This is the schema specified in AGENT.md Step 7 Fix 2. Previously the
        parser only accepted the v1 dict schema and silently dropped list
        entries — a P0 bug where LLM-generated v2 comments would produce
        zero-comment DOCX output. Fix 2026-04-11: accept both schemas.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            unpacked_dir = Path(tmpdir) / "unpacked"
            self._write_minimal_docx_package(unpacked_dir)

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps({
                    "mappings": [
                        {"clause_id": "clause-001", "mapped": True, "paragraph_indices": [0]}
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            comments_path = Path(tmpdir) / "comments.json"
            comments_path.write_text(
                json.dumps({
                    "_meta": {
                        "reviewer_author": "Contract Review Specialist",
                        "reviewer_initials": "CRS",
                    },
                    # v2 schema: array of {audience, text}
                    "clause-001": [
                        {
                            "audience": "EXTERNAL",
                            "text": "[EXTERNAL] Performance bond cap is above market.",
                        },
                        {
                            "audience": "INTERNAL",
                            "text": "[INTERNAL] Fallback: 100% → 50% → direct damages only.",
                        },
                    ],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = apply_comments_module.apply_comments(
                str(unpacked_dir),
                str(clause_map_path),
                str(comments_path),
            )

            self.assertTrue(result["success"], result)
            self.assertEqual(result["total_comments"], 2)
            self.assertEqual(result["total_clause_comments"], 2)
            self.assertEqual(result["comments_applied"], 2)
            self.assertEqual(result["reviewer"]["author"], "Contract Review Specialist")

            comments_tree = ET.parse(unpacked_dir / "word" / "comments.xml")
            comments_root = comments_tree.getroot()
            comments = comments_root.findall(f"{{{W_NS}}}comment")
            self.assertEqual(len(comments), 2)

            # Verify the audience prefixes landed correctly in the XML
            texts = [c.find(f".//{{{W_NS}}}t").text for c in comments]
            self.assertTrue(any("[EXTERNAL]" in t for t in texts))
            self.assertTrue(any("[INTERNAL]" in t for t in texts))

    def test_apply_comments_partial_external_mapping_failure_halts(self):
        """A failed EXTERNAL comment must halt even if other comments apply."""
        with tempfile.TemporaryDirectory() as tmpdir:
            unpacked_dir = Path(tmpdir) / "unpacked"
            self._write_minimal_docx_package(unpacked_dir)

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps({
                    "mappings": [
                        {"clause_id": "clause-001", "mapped": True, "paragraph_indices": [0]}
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            comments_path = Path(tmpdir) / "comments.json"
            comments_path.write_text(
                json.dumps({
                    "clause-001": [
                        {
                            "audience": "INTERNAL",
                            "text": "[INTERNAL] This mapped comment should land.",
                        }
                    ],
                    "clause-002": [
                        {
                            "audience": "EXTERNAL",
                            "text": "[EXTERNAL] This high-risk comment has no mapping.",
                        }
                    ],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = apply_comments_module.apply_comments(
                str(unpacked_dir),
                str(clause_map_path),
                str(comments_path),
            )

            self.assertFalse(result["success"], result)
            self.assertEqual(result["comments_applied"], 1)
            self.assertEqual(result["failed_entries"], 1)
            self.assertEqual(result["failed_critical_or_high"], 1)
            self.assertEqual(result["failures"][0]["clause_id"], "clause-002")
            self.assertEqual(result["failures"][0]["reason"], "mapping_missing")

    def test_apply_comments_fail_loud_on_unknown_audience(self):
        """v2 schema with unknown audience values must fail loudly.

        Previously, if every comment entry had an unknown audience (e.g. LLM
        typo "external" lowercase, or "EXT" abbreviation), every entry would
        be silently skipped and success: True returned. Fix 2026-04-11:
        total_clause_comments tracks intent; if intent > 0 but applied == 0,
        return success: False.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            unpacked_dir = Path(tmpdir) / "unpacked"
            self._write_minimal_docx_package(unpacked_dir)

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps({
                    "mappings": [
                        {"clause_id": "clause-001", "mapped": True, "paragraph_indices": [0]}
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            comments_path = Path(tmpdir) / "comments.json"
            comments_path.write_text(
                json.dumps({
                    "_meta": {"reviewer_author": "Reviewer"},
                    "clause-001": [
                        # Unknown audience → silently dropped by builder but
                        # still counted toward total_clause_comments.
                        {"audience": "typo", "text": "Should not land."},
                    ],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = apply_comments_module.apply_comments(
                str(unpacked_dir),
                str(clause_map_path),
                str(comments_path),
            )

            # Must fail loudly, not silently succeed
            self.assertFalse(result["success"], result)
            self.assertIn("error", result)
            self.assertIn("audience", result["error"].lower())
            self.assertEqual(result["comments_applied"], 0)
            self.assertEqual(result["total_clause_comments"], 1)

    def test_apply_comments_legitimate_empty_is_success(self):
        """Empty comments.json (only _meta) is a legitimate no-op and must
        return success: True. Loose review mode or all-Acceptable contracts
        may produce zero comment entries, which is not a failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            unpacked_dir = Path(tmpdir) / "unpacked"
            self._write_minimal_docx_package(unpacked_dir)

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps({"mappings": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            comments_path = Path(tmpdir) / "comments.json"
            comments_path.write_text(
                json.dumps({"_meta": {"reviewer_author": "Reviewer"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = apply_comments_module.apply_comments(
                str(unpacked_dir),
                str(clause_map_path),
                str(comments_path),
            )

            self.assertTrue(result["success"], result)
            self.assertEqual(result["comments_applied"], 0)
            self.assertEqual(result["total_clause_comments"], 0)


class SessionDAudit009RedlinesTests(unittest.TestCase):
    def test_apply_redlines_preserves_existing_revisions_and_only_tracks_changed_substring(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            document_path = Path(tmpdir) / "document.xml"
            write_file(
                document_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:commentRangeStart w:id="9"/>
      <w:r><w:t>Reviewed clause</w:t></w:r>
      <w:commentRangeEnd w:id="9"/>
      <w:r><w:commentReference w:id="9"/></w:r>
      <w:ins w:id="7" w:author="Existing Reviewer" w:date="2026-03-27T00:00:00Z">
        <w:r><w:t>Existing insertion</w:t></w:r>
      </w:ins>
    </w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Seller shall pay within 30 days.</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
""",
            )

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps(
                    {
                        "mappings": [
                            {"clause_id": "clause-001", "mapped": True, "paragraph_indices": [1]}
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            redlines_path = Path(tmpdir) / "redlines.json"
            redlines_path.write_text(
                json.dumps(
                    {
                        "_meta": {
                            "reviewer_author": "Client Legal",
                            "reviewer_initials": "CL",
                        },
                        "clause-001": {
                            "suggested_redline": "Seller shall pay within 10 days."
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = apply_redlines_module.apply_redlines(
                str(document_path),
                str(clause_map_path),
                str(redlines_path),
                str(document_path),
            )

            self.assertTrue(result["success"], result)
            self.assertEqual(result["applied_count"], 1)
            self.assertEqual(result["paragraphs_touched"], 1)
            self.assertEqual(result["reviewer"]["author"], "Client Legal")

            paragraphs = direct_paragraphs(document_path)
            self.assertEqual(
                paragraphs[0].find(f".//{{{W_NS}}}ins").get(f"{{{W_NS}}}author"),
                "Existing Reviewer",
            )
            self.assertIsNotNone(paragraphs[0].find(f".//{{{W_NS}}}commentRangeStart"))

            second_paragraph_xml = ET.tostring(paragraphs[1], encoding="unicode")
            self.assertIn("Seller shall pay within ", second_paragraph_xml)
            self.assertIn("<w:delText", second_paragraph_xml)
            self.assertIn(">30<", second_paragraph_xml)
            self.assertIn("<w:ins", second_paragraph_xml)
            self.assertIn('w:author="Client Legal"', second_paragraph_xml)
            self.assertIn(">10<", second_paragraph_xml)
            self.assertIn("> days.<", second_paragraph_xml)
            self.assertNotIn("Seller shall pay within 30 days.</w:delText>", second_paragraph_xml)

    def test_apply_redlines_can_update_multiple_mapped_paragraphs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            document_path = Path(tmpdir) / "document.xml"
            write_file(
                document_path,
                """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Seller shall notify Buyer.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Payment is due within 30 days.</w:t></w:r></w:p>
  </w:body>
</w:document>
""",
            )

            clause_map_path = Path(tmpdir) / "clause-map.json"
            clause_map_path.write_text(
                json.dumps(
                    {
                        "mappings": [
                            {"clause_id": "clause-002", "mapped": True, "paragraph_indices": [0, 1]}
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            redlines_path = Path(tmpdir) / "redlines.json"
            redlines_path.write_text(
                json.dumps(
                    {
                        "clause-002": {
                            "suggested_redline": "Seller shall promptly notify Buyer.\n\nPayment is due within 10 days."
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = apply_redlines_module.apply_redlines(
                str(document_path),
                str(clause_map_path),
                str(redlines_path),
                str(document_path),
            )

            self.assertTrue(result["success"], result)
            self.assertEqual(result["applied_count"], 1)
            self.assertEqual(result["paragraphs_touched"], 2)

            paragraphs = direct_paragraphs(document_path)
            para_texts = [ET.tostring(paragraph, encoding="unicode") for paragraph in paragraphs]
            self.assertIn("promptly", para_texts[0])
            self.assertIn(">30<", para_texts[1])
            self.assertIn(">10<", para_texts[1])


class SessionDAudit011ReportTests(unittest.TestCase):
    def test_compile_report_renders_korean_memorandum_style_docx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "ko",
                        "general_review_mode": True,
                        "contract_info": {
                            "title": "소프트웨어 라이선스 계약",
                            "contract_family": "license",
                        },
                        "memo_metadata": {
                            "date": "2026-03-27",
                            "recipient": "주식회사 예시",
                            "reference": "법무팀장",
                            "sender": "Legal Workflow Orchestrator",
                            "subject": "소프트웨어 라이선스 계약 검토 의견서",
                            "signer": "계약 검토 스페셜리스트",
                        },
                        "background_facts": [
                            "귀사는 상대방이 제시한 소프트웨어 라이선스 계약 초안을 검토 요청하였습니다."
                        ],
                        "questions_presented": [
                            "책임 제한 조항의 적정성",
                            "계약 해지 조항의 균형성",
                        ],
                        "executive_summary": {
                            "overall_risk": "high",
                            "recommendation": "책임 제한과 해지 조항은 수정 협의가 필요할 것으로 사료됩니다.",
                            "risk_distribution": {
                                "critical": 0,
                                "high": 1,
                                "medium": 0,
                                "low": 0,
                                "acceptable": 0,
                            },
                            "key_issues": [
                                "책임 제한 예외가 과도합니다.",
                                "상대방의 임의 해지 권한이 넓습니다."
                            ],
                        },
                        "clauses": [
                            {
                                "clause_id": "clause-001",
                                "section_no": "제5조",
                                "heading": "책임 제한",
                                "clause_type": "liability_cap",
                                "risk_level": "high",
                                "risk_rationale": "상대방의 고의·중과실 외에도 광범위한 예외가 인정되어 책임 제한 기능이 약화됩니다.",
                                "divergence": "통상적인 상호 책임 제한 구조보다 상대방에 유리합니다.",
                                "playbook_tier": "fallback",
                                "playbook_missing": False,
                                "suggested_redline": "각 당사자의 총 책임은 최근 12개월간 지급된 대가를 한도로 합니다.",
                                "internal_note": "최소한 간접손해 배제와 cap linkage는 확보할 필요가 있습니다.",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )

            result = json.loads(completed.stdout)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["report_language"], "ko")
            self.assertTrue(output_docx.exists())

            document_xml = read_zip_text(output_docx, "word/document.xml")
            self.assertIn("MEMORANDUM", document_xml)
            self.assertIn("수 신", document_xml)
            self.assertIn("발 신", document_xml)
            self.assertIn("제 목", document_xml)
            self.assertIn("질의의 배경", document_xml)
            self.assertIn("질의 사항", document_xml)
            self.assertIn("법률 의견의 한계", document_xml)
            self.assertIn("검토의견", document_xml)
            self.assertIn("결론", document_xml)
            self.assertIn("Malgun Gothic", document_xml)
            self.assertIn('w:w="11905"', document_xml)
            self.assertIn('w:h="16837"', document_xml)
            self.assertNotIn("<w:i/>", document_xml)
            self.assertNotIn("FF6600", document_xml)
            self.assertIn("일반 계약 검토 기준에 따라 작성되었습니다", document_xml)
            self.assertIn("계약 검토 스페셜리스트", document_xml)

    def test_compile_report_keeps_generic_renderer_for_english_reports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "en",
                        "contract_info": {"title": "SaaS Agreement", "contract_family": "saas"},
                        "executive_summary": {
                            "overall_risk": "medium",
                            "risk_distribution": {
                                "critical": 0,
                                "high": 0,
                                "medium": 1,
                                "low": 0,
                                "acceptable": 0,
                            },
                            "key_issues": ["Liability cap is below market."],
                            "recommendation": "Revise liability and termination terms.",
                        },
                        "clauses": [
                            {
                                "clause_id": "clause-001",
                                "heading": "Liability",
                                "risk_level": "medium",
                                "risk_rationale": "Cap is too low.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["report_language"], "en")

            document_xml = read_zip_text(output_docx, "word/document.xml")
            self.assertIn("Executive Summary", document_xml)
            self.assertIn("Per-Clause Analysis", document_xml)
            self.assertNotIn("Section 1. Executive Summary", document_xml)
            self.assertNotIn("Section 6. Clause-by-Clause Analysis", document_xml)

    def test_compile_report_uses_numbered_sections_when_negotiation_priority_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            matter_working_dir = Path(tmpdir) / "working"
            trace_path = matter_working_dir / "baseline-context" / "loaded.json"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text(
                json.dumps(
                    {
                        "loaded_at": "2026-04-10T12:34:56Z",
                        "source": "agent-prepipe",
                        "files_loaded": [
                            {
                                "name": "review-guide.md",
                                "byte_size": 12345,
                                "sha256_short": "abc12345",
                                "last_section_heading": "Section 5 — Review Notes",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "en",
                        "review_mode": "strict",
                        "contract_info": {
                            "title": "EPC Supply Agreement",
                            "contract_family": "supply_agreement",
                            "language": "en",
                            "jurisdiction": "Singapore",
                            "governing_law": "England & Wales",
                        },
                        "executive_summary": {
                            "overview": "This EPC supply agreement governs the delivery of key plant equipment and allocates major schedule and performance risk.",
                            "overall_risk": "high",
                            "risk_distribution": {
                                "critical": 5,
                                "high": 11,
                                "medium": 6,
                                "low": 2,
                                "acceptable": 3,
                            },
                            "key_issues": [
                                "[§4] Performance Bond cap — exposure is uncapped.",
                                "[§13] Liquidated damages — cap is missing.",
                                "[§22] Termination — convenience right is one-sided.",
                            ],
                            "negotiation_priority": {
                                "must_haves": ["[§4] Cap the performance bond."],
                                "should_haves": ["[§18] Broaden force majeure relief."],
                                "nice_to_haves": ["[§29] Add a change-of-control carve-out."],
                            },
                            "review_notes": [
                                "Library mode: House position comparison active",
                                "Review date: 2026-04-10",
                            ],
                            "recommendation": "Negotiate the critical allocation points before signing.",
                        },
                        "clauses": [make_clause(index, include_action=True) for index in range(1, 28)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                    str(matter_working_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["report_language"], "en")
            self.assertEqual(result["clauses_count"], 27)

            document_xml = read_zip_text(output_docx, "word/document.xml")
            self.assertIn("Section 1. Executive Summary", document_xml)
            self.assertIn("Section 2. Overall Risk Assessment", document_xml)
            self.assertIn("Section 3. Key Issues", document_xml)
            self.assertIn("Section 4. Negotiation Priority", document_xml)
            self.assertIn("4.1 Must-haves (Critical)", document_xml)
            self.assertIn("4.2 Should-haves (High)", document_xml)
            self.assertIn("4.3 Nice-to-haves (Medium)", document_xml)
            self.assertIn("Section 5. Review Notes", document_xml)
            self.assertIn("Section 6. Clause-by-Clause Analysis", document_xml)
            self.assertNotIn("Per-Clause Analysis", document_xml)
            self.assertEqual(document_xml.count("Clause Type: "), 27)
            self.assertIn("Baselines applied:", document_xml)

    def test_compile_report_renders_all_korean_clauses_when_many_are_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "ko",
                        "contract_info": {
                            "title": "EPC 공급계약",
                            "contract_family": "supply_agreement",
                        },
                        "memo_metadata": {
                            "date": "2026-04-10",
                            "recipient": "주식회사 예시",
                            "sender": "Legal Workflow Orchestrator",
                            "subject": "EPC 공급계약 검토 의견서",
                            "signer": "계약 검토 스페셜리스트",
                        },
                        "executive_summary": {
                            "overall_risk": "high",
                            "risk_distribution": {
                                "critical": 0,
                                "high": 5,
                                "medium": 22,
                                "low": 0,
                                "acceptable": 0,
                            },
                            "recommendation": "핵심 위험 조항의 수정 협의가 필요합니다.",
                            "key_issues": [
                                "성능보증 조항이 과도합니다.",
                                "손해배상 한도가 불명확합니다.",
                            ],
                            "negotiation_priority": {
                                "must_haves": ["성능보증 상한 설정"],
                                "should_haves": ["손해배상 구조 정비"],
                                "nice_to_haves": ["통지 절차 정비"],
                            },
                        },
                        "clauses": [make_clause(index, korean=True) for index in range(1, 28)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["report_language"], "ko")
            self.assertEqual(result["clauses_count"], 27)

            document_xml = read_zip_text(output_docx, "word/document.xml")
            self.assertIn("4. 검토의견", document_xml)
            self.assertEqual(document_xml.count("위험도:"), 27)
            self.assertIn("제1조 Clause 1", document_xml)
            self.assertIn("제27조 Clause 27", document_xml)
            # Korean negotiation priority sub-section (v2 schema)
            self.assertIn("가. 협상 우선순위", document_xml)
            self.assertIn("(1) 반드시 수정 사항", document_xml)
            self.assertIn("(2) 협상 추진 사항", document_xml)
            self.assertIn("(3) 여력 있을 시 제기 사항", document_xml)
            self.assertIn("성능보증 상한 설정", document_xml)
            self.assertIn("손해배상 구조 정비", document_xml)
            self.assertIn("통지 절차 정비", document_xml)
            self.assertIn("나. 조항별 분석", document_xml)

    def test_compile_report_korean_without_negotiation_priority_uses_legacy_structure(self):
        """Backward compat: Korean review.json without negotiation_priority
        should render the legacy 5-section memorandum with no 가./나.
        sub-headings under 4. 검토의견."""
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "ko",
                        "contract_info": {
                            "title": "기존 형식 계약",
                            "contract_family": "nda",
                        },
                        "memo_metadata": {
                            "date": "2026-04-10",
                            "recipient": "주식회사 예시",
                            "sender": "Legal Workflow Orchestrator",
                            "subject": "기존 형식 검토 의견서",
                            "signer": "계약 검토 스페셜리스트",
                        },
                        "executive_summary": {
                            "overall_risk": "medium",
                            "risk_distribution": {
                                "critical": 0,
                                "high": 5,
                                "medium": 0,
                                "low": 0,
                                "acceptable": 0,
                            },
                            "recommendation": "조항별 검토 결과를 반영하시기 바랍니다.",
                            "key_issues": ["예시 이슈"],
                            # negotiation_priority intentionally omitted
                        },
                        "clauses": [make_clause(index, korean=True) for index in range(1, 6)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["report_language"], "ko")
            self.assertEqual(result["clauses_count"], 5)

            document_xml = read_zip_text(output_docx, "word/document.xml")
            self.assertIn("4. 검토의견", document_xml)
            self.assertEqual(document_xml.count("위험도:"), 5)
            # Backward compat: legacy Korean memo has no Korean sub-headings
            self.assertNotIn("가. 협상 우선순위", document_xml)
            self.assertNotIn("나. 조항별 분석", document_xml)

    def test_contract_language_en_does_not_force_english_report(self):
        """Regression guard for report-language fallback drift.

        If the review JSON has contract_info.language = "en" (the CONTRACT's
        own language set by Step 2) but no report_language, the resolver
        MUST NOT treat this as an English report request. Instead, it should
        fall back to Hangul detection on the recommendation / overview text.
        A Korean attorney reviewing an English contract should see a Korean
        memorandum as long as the review text itself is in Korean.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        # Deliberately omit report_language to simulate an LLM
                        # that forgot to copy Pre-Pipeline intake item 3 into
                        # the review JSON.
                        "contract_info": {
                            "title": "English Supply Agreement",
                            "contract_family": "supply_agreement",
                            "language": "en",  # ← must NOT force English report
                        },
                        "memo_metadata": {
                            "date": "2026-04-11",
                            "recipient": "주식회사 예시",
                            "sender": "Legal Workflow Orchestrator",
                            "subject": "영문 공급계약 검토 의견서",
                            "signer": "계약 검토 스페셜리스트",
                        },
                        "executive_summary": {
                            "overall_risk": "high",
                            "risk_distribution": {
                                "critical": 0,
                                "high": 3,
                                "medium": 0,
                                "low": 0,
                                "acceptable": 0,
                            },
                            "recommendation": "본 영문 공급계약은 핵심 위험 조항의 수정이 필요합니다.",
                            "key_issues": [
                                "성능보증 조항이 과도합니다.",
                                "손해배상 한도가 불명확합니다.",
                            ],
                        },
                        "clauses": [make_clause(index, korean=True) for index in range(1, 4)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertTrue(result["success"], result)
            # The resolver should pick Korean via Hangul heuristic, NOT English
            # via contract_info.language.
            self.assertEqual(result["report_language"], "ko")

            document_xml = read_zip_text(output_docx, "word/document.xml")
            # Must render as Korean memorandum, not English Executive Summary
            self.assertIn("4. 검토의견", document_xml)
            self.assertNotIn("Executive Summary", document_xml)
            self.assertNotIn("Per-Clause Analysis", document_xml)

    def test_clause_count_mismatch_fails_by_default(self):
        """Regression guard for silently truncated clause output.

        When risk_distribution totals N but data.clauses has fewer than N
        entries, the compiler must fail closed by default instead of emitting
        a plausible but incomplete DOCX.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "en",
                        "review_mode": "strict",
                        "contract_info": {
                            "title": "Large EPC Contract",
                            "contract_family": "supply_agreement",
                            "language": "en",
                        },
                        "executive_summary": {
                            "overview": "Large EPC supply agreement.",
                            "overall_risk": "critical",
                            "risk_distribution": {
                                "critical": 5, "high": 11, "medium": 6,
                                "low": 2, "acceptable": 3,
                            },
                            "key_issues": ["[§4] Performance Bond cap."],
                            "negotiation_priority": {
                                "must_haves": ["[§4] Cap the performance bond."],
                                "should_haves": [],
                                "nice_to_haves": [],
                            },
                            "review_notes": ["Review date: 2026-04-11"],
                        },
                        "clauses": [make_clause(index, include_action=True) for index in range(1, 11)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(result["success"], result)
            self.assertIn("Clause completeness validation failed", result["error"])
            self.assertIn("27", result["error"])
            self.assertIn("10", result["error"])
            self.assertFalse(output_docx.exists())

    def test_clause_count_mismatch_can_render_with_allow_incomplete(self):
        """Legacy escape hatch: warning rendering remains available only when
        the operator explicitly passes --allow-incomplete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            review_data_path = Path(tmpdir) / "review-data.json"
            output_docx = Path(tmpdir) / "report.docx"
            review_data_path.write_text(
                json.dumps(
                    {
                        "report_language": "ko",
                        "contract_info": {
                            "title": "대형 EPC 계약",
                            "contract_family": "supply_agreement",
                        },
                        "memo_metadata": {
                            "date": "2026-04-11",
                            "recipient": "주식회사 예시",
                            "sender": "Legal Workflow Orchestrator",
                            "subject": "EPC 계약 검토 의견서",
                            "signer": "계약 검토 스페셜리스트",
                        },
                        "executive_summary": {
                            "overall_risk": "critical",
                            "recommendation": "기존 결론 텍스트입니다.",
                            "risk_distribution": {
                                "critical": 3, "high": 7, "medium": 3,
                                "low": 1, "acceptable": 1,
                            },
                            "key_issues": ["성능보증 조항"],
                        },
                        "clauses": [make_clause(index, korean=True) for index in range(1, 6)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / ".claude/skills/report-compiler/scripts/compile-report.js"),
                    str(review_data_path),
                    str(output_docx),
                    "--allow-incomplete",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(completed.stdout)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["report_language"], "ko")

            document_xml = read_zip_text(output_docx, "word/document.xml")
            self.assertIn("CLAUSE COUNT MISMATCH", document_xml)
            self.assertIn("15", document_xml)
            self.assertIn("INCOMPLETE", document_xml)
            self.assertIn("기존 결론 텍스트입니다", document_xml)


if __name__ == "__main__":
    unittest.main()

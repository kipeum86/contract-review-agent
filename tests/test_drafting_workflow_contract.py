import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPILE_DRAFT = REPO_ROOT / ".claude" / "skills" / "report-compiler" / "scripts" / "compile-draft.js"


def read_docx_member(docx_path: Path, member: str) -> str:
    with zipfile.ZipFile(docx_path, "r") as archive:
        return archive.read(member).decode("utf-8")


def sample_draft(include_self_review_notes: bool = False) -> dict:
    return {
        "draft_metadata": {
            "title": "Mutual Non-Disclosure Agreement",
            "parties": ["Alpha Inc.", "Beta LLC"],
            "contract_type": "nda",
            "language": "en",
            "matter_id": "draft-nda-001",
            "date_created": "2026-04-26",
        },
        "defined_terms": ["Confidential Information"],
        "contract_text": {
            "preamble": "This Agreement is entered into by Alpha Inc. and Beta LLC.",
            "signature_blocks": [
                {
                    "party": "Alpha Inc.",
                    "date": "[Date]",
                    "signature_line": "____________________",
                },
                {
                    "party": "Beta LLC",
                    "date": "[Date]",
                    "signature_line": "____________________",
                },
            ],
        },
        "sections": [
            {
                "section_number": 1,
                "title": "Confidentiality",
                "text": "Each party shall protect Confidential Information.",
                "subsections": [
                    {
                        "number": 1,
                        "title": "Permitted Use",
                        "text": "Confidential Information may be used only for the Purpose.",
                    }
                ],
            }
        ],
        "self_review": {
            "issues": [
                {
                    "severity": "medium",
                    "section": "1",
                    "description": "Confirm whether a residuals clause is desired.",
                    "suggested_fix": "Add only if commercially intended.",
                }
            ]
        },
        "output_options": {
            "include_self_review_notes": include_self_review_notes,
        },
    }


class DraftingWorkflowContractTests(unittest.TestCase):
    def test_compile_draft_help_smoke(self):
        result = subprocess.run(
            ["node", str(COMPILE_DRAFT), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["usage"], "compile-draft.js <draft.json> <output.docx>")
        self.assertIn("sections[]", payload["required_fields"])

    def test_compile_draft_renders_official_docx_without_internal_notes_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft.json"
            output_path = Path(tmpdir) / "draft.docx"
            draft_path.write_text(
                json.dumps(sample_draft(include_self_review_notes=False), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["node", str(COMPILE_DRAFT), str(draft_path), str(output_path)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["success"])
            self.assertFalse(payload["self_review_notes_included"])
            self.assertEqual(payload["sections_count"], 1)
            self.assertTrue(output_path.exists())

            document_xml = read_docx_member(output_path, "word/document.xml")
            self.assertIn("Mutual Non-Disclosure Agreement", document_xml)
            self.assertIn("Article 1", document_xml)
            self.assertIn("Confidentiality", document_xml)
            self.assertIn("Alpha Inc.", document_xml)
            self.assertNotIn("[INTERNAL] Self-Review Notes", document_xml)
            self.assertNotIn("Confirm whether a residuals clause is desired", document_xml)

    def test_compile_draft_can_include_self_review_notes_for_internal_working_draft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft-internal.json"
            output_path = Path(tmpdir) / "draft-internal.docx"
            draft_path.write_text(
                json.dumps(sample_draft(include_self_review_notes=True), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["node", str(COMPILE_DRAFT), str(draft_path), str(output_path)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["self_review_notes_included"])
            document_xml = read_docx_member(output_path, "word/document.xml")
            self.assertIn("[INTERNAL] Self-Review Notes", document_xml)
            self.assertIn("Confirm whether a residuals clause is desired", document_xml)

    def test_compile_draft_rejects_incomplete_draft_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "invalid-draft.json"
            output_path = Path(tmpdir) / "invalid.docx"
            draft_path.write_text(
                json.dumps({"draft_metadata": {"title": "Missing fields"}, "sections": []}),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["node", str(COMPILE_DRAFT), str(draft_path), str(output_path)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stderr.strip().splitlines()[-1])
            self.assertIn("Invalid draft.json", payload["error"])
            self.assertFalse(output_path.exists())

    def test_drafting_docs_share_official_artifact_contract(self):
        drafting_agent = (REPO_ROOT / ".claude" / "agents" / "drafting-agent" / "AGENT.md").read_text(encoding="utf-8")
        draft_command = (REPO_ROOT / ".claude" / "commands" / "draft.md").read_text(encoding="utf-8")
        report_compiler = (REPO_ROOT / ".claude" / "skills" / "report-compiler" / "SKILL.md").read_text(encoding="utf-8")

        for artifact in [
            "working/draft.json",
            "working/draft_assumptions.md",
            "output/draft.docx",
            "working/pipeline-state.json",
        ]:
            self.assertIn(artifact, drafting_agent)
            self.assertIn(artifact, draft_command)

        self.assertIn("compile-draft.js", report_compiler)
        self.assertNotIn("does **not** yet include a dedicated Workflow 5", report_compiler)
        self.assertIn("not part of the default `/draft` success contract", draft_command)


if __name__ == "__main__":
    unittest.main()

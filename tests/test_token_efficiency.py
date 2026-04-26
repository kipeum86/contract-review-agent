import importlib.util
import json
import os
import shutil
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
    "query_index_token_efficiency",
    ".claude/skills/index-manager/scripts/query-index.py",
)


class TokenEfficiencyTests(unittest.TestCase):
    def write_reference_bundle(self, root: Path) -> None:
        refs_dir = root / ".claude" / "skills" / "review-domain-knowledge" / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "review-guide.md").write_text(
            "\n".join(
                [
                    "# Review Guide",
                    "",
                    "## Risk Grading Criteria",
                    "",
                    "### Critical",
                    "Critical guidance.",
                    "",
                    "### High",
                    "High guidance.",
                    "",
                    "## Analysis Methodology",
                    "",
                    "Method details that should not appear in the risk-only section.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (refs_dir / "audience-firewall.md").write_text(
            "\n".join(
                [
                    "# Audience Firewall",
                    "",
                    "## What MUST NOT appear",
                    "",
                    "Internal-only wording.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @unittest.skipIf(shutil.which("jq") is None, "jq is required by the loader script")
    def test_domain_reference_loader_digest_and_section_modes(self):
        script = REPO_ROOT / ".claude" / "scripts" / "load-domain-references.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            self.write_reference_bundle(temp_root)
            env = {
                **os.environ,
                "CLAUDE_PROJECT_DIR": str(temp_root),
                "LOADER_SOURCE": "test",
            }

            digest = subprocess.run(
                ["bash", str(script), "review", "--mode=digest"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(digest.returncode, 0, digest.stderr)
            self.assertIn("DIGEST ONLY", digest.stdout)
            self.assertIn("Loader mode: digest", digest.stdout)
            self.assertIn("Bundle sha256:", digest.stdout)
            self.assertIn("Available headings:", digest.stdout)
            self.assertNotIn("Critical guidance.", digest.stdout)

            trace_line = next(
                line for line in digest.stdout.splitlines()
                if line.startswith("TRACE: ")
            )
            trace = json.loads(Path(trace_line.removeprefix("TRACE: ")).read_text(encoding="utf-8"))
            self.assertEqual(trace["loader_mode"], "digest")
            self.assertEqual(trace["source"], "test")
            self.assertTrue(trace["bundle_sha256"])

            section = subprocess.run(
                [
                    "bash",
                    str(script),
                    "review",
                    "--mode=section",
                    "--section=Risk Grading Criteria",
                    "--file=review-guide.md",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(section.returncode, 0, section.stderr)
            self.assertIn("Loader mode: section", section.stdout)
            self.assertIn("## Risk Grading Criteria", section.stdout)
            self.assertIn("### Critical", section.stdout)
            self.assertIn("Critical guidance.", section.stdout)
            self.assertNotIn("## Analysis Methodology", section.stdout)

    def test_query_summary_mode_caps_and_hydrates_only_selected_candidates(self):
        original_load_json = query_module.load_json
        original_load_yaml = query_module.load_yaml

        clauses_index = {
            "clauses": [
                {
                    "doc_id": "doc-1",
                    "clause_id": "clause-001",
                    "heading": "Preferred liability",
                    "contract_family": "nda",
                    "clause_type": "liability",
                    "doc_class": "template",
                    "authority_level": "preferred",
                    "approval_state": "approved",
                    "status": "active",
                    "language": "en",
                },
                {
                    "doc_id": "doc-2",
                    "clause_id": "clause-002",
                    "heading": "Fallback liability",
                    "contract_family": "nda",
                    "clause_type": "liability",
                    "doc_class": "template",
                    "authority_level": "fallback",
                    "approval_state": "approved",
                    "status": "active",
                    "language": "en",
                },
                {
                    "doc_id": "doc-3",
                    "clause_id": "clause-003",
                    "heading": "Termination",
                    "contract_family": "nda",
                    "clause_type": "termination",
                    "approval_state": "approved",
                    "status": "active",
                },
            ]
        }
        clause_texts = {
            "doc-1::clause-001": "Full preferred liability clause text.",
            "doc-2::clause-002": "Full fallback liability clause text.",
        }
        retrieval_config = {
            "priority_order": {
                "1": "preferred_template",
                "2": "approved_precedent",
                "3": "fallback_template",
            },
            "filter_rules": {
                "stage_3_affinity": {"minimum_exact_candidates": 0},
            },
        }

        try:
            def fake_load_json(path):
                if str(path).endswith("clauses.json"):
                    return clauses_index
                if str(path).endswith("clause-texts.json"):
                    return {"texts": clause_texts}
                return None

            query_module.load_json = fake_load_json
            query_module.load_yaml = lambda path: retrieval_config

            summary = query_module.query(
                contract_family="nda",
                target_clauses=[{"clause_type": "liability"}],
                summary_only=True,
                top_k=1,
            )

            self.assertTrue(summary["summary_only"])
            self.assertEqual(summary["top_k"], 1)
            self.assertEqual(summary["total_candidates"], 1)
            candidates = summary["candidates"]["liability"]
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["candidate_id"], "doc-1::clause-001")
            self.assertFalse(candidates[0]["hydrated"])
            self.assertNotIn("text", candidates[0])

            hydrated = query_module.query(
                contract_family="nda",
                target_clauses=[{"clause_type": "liability"}],
                summary_only=True,
                top_k=2,
                hydrate_candidate_ids=["doc-2::clause-002"],
            )

            hydrated_candidates = hydrated["candidates"]["liability"]
            by_id = {candidate["candidate_id"]: candidate for candidate in hydrated_candidates}
            self.assertFalse(by_id["doc-1::clause-001"]["hydrated"])
            self.assertNotIn("text", by_id["doc-1::clause-001"])
            self.assertTrue(by_id["doc-2::clause-002"]["hydrated"])
            self.assertEqual(
                by_id["doc-2::clause-002"]["text"],
                "Full fallback liability clause text.",
            )
        finally:
            query_module.load_json = original_load_json
            query_module.load_yaml = original_load_yaml


if __name__ == "__main__":
    unittest.main()

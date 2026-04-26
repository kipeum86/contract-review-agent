import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / ".claude/scripts/validate-json-artifact.py"
SCHEMAS_DIR = REPO_ROOT / ".claude/schemas"


def run_validator(schema_name: str, payload: dict) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "artifact.json"
        input_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--schema",
                str(SCHEMAS_DIR / schema_name),
                "--input",
                str(input_path),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


class ArtifactSchemaValidationTests(unittest.TestCase):
    def test_review_schema_accepts_complete_v1_artifact(self):
        payload = {
            "schema_version": 1,
            "report_language": "en",
            "review_mode": "moderate",
            "general_review_mode": False,
            "contract_info": {
                "title": "SaaS Agreement",
                "contract_family": "saas",
                "language": "en",
            },
            "executive_summary": {
                "overview": "This SaaS agreement allocates subscription and data risk.",
                "overall_risk": "high",
                "risk_distribution": {
                    "critical": 0,
                    "high": 1,
                    "medium": 0,
                    "low": 0,
                    "acceptable": 0,
                },
                "key_issues": ["Liability cap is not aligned with market."],
                "negotiation_priority": {
                    "must_haves": ["Cap liability exclusions."],
                    "should_haves": [],
                    "nice_to_haves": [],
                },
                "review_notes": ["Library mode: House position comparison active"],
            },
            "clauses": [
                {
                    "clause_id": "clause-001",
                    "heading": "Liability",
                    "clause_type": "liability_cap",
                    "risk_level": "high",
                    "risk_rationale": "The exclusion is too broad.",
                }
            ],
        }

        completed = run_validator("review.schema.json", payload)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["success"])

    def test_review_schema_rejects_missing_risk_distribution(self):
        payload = {
            "schema_version": 1,
            "report_language": "en",
            "review_mode": "moderate",
            "contract_info": {
                "title": "SaaS Agreement",
                "contract_family": "saas",
                "language": "en",
            },
            "executive_summary": {
                "overview": "Overview.",
                "overall_risk": "high",
                "key_issues": [],
                "negotiation_priority": {
                    "must_haves": [],
                    "should_haves": [],
                    "nice_to_haves": [],
                },
                "review_notes": [],
            },
            "clauses": [],
        }

        completed = run_validator("review.schema.json", payload)
        self.assertNotEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertFalse(result["success"])
        self.assertTrue(
            any("risk_distribution" in error for error in result["errors"]),
            result,
        )

    def test_redlines_schema_rejects_wrong_field_name(self):
        payload = {
            "_meta": {"reviewer_author": "Client Legal"},
            "clause-001": {"redline": "Use the wrong field name."},
        }

        completed = run_validator("redlines.schema.json", payload)
        self.assertNotEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertTrue(
            any("suggested_redline" in error for error in result["errors"]),
            result,
        )

    def test_comments_schema_rejects_audience_prefix_mismatch(self):
        payload = {
            "clause-001": [
                {
                    "audience": "EXTERNAL",
                    "text": "[INTERNAL] Fallback position should not be external.",
                }
            ]
        }

        completed = run_validator("comments.schema.json", payload)
        self.assertNotEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertTrue(
            any("prefix must match audience" in error for error in result["errors"]),
            result,
        )


if __name__ == "__main__":
    unittest.main()

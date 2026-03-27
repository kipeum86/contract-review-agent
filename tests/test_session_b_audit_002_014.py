import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


batch_module = load_module("batch_classify_and_publish", "scripts/batch_classify_and_publish.py")
supersession_module = load_module(
    "supersession_module",
    ".claude/skills/index-manager/scripts/supersession.py",
)


def write_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.dump(manifest, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def build_run_package(run_dir: Path, manifest: dict) -> None:
    (run_dir / "normalized").mkdir(parents=True, exist_ok=True)
    (run_dir / "structure").mkdir(exist_ok=True)
    (run_dir / "clauses").mkdir(exist_ok=True)
    (run_dir / "quality").mkdir(exist_ok=True)

    (run_dir / "classification.json").write_text(
        json.dumps({"doc_class": manifest["doc_class"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "manifest.yaml").write_text(
        yaml.dump(manifest, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    (run_dir / "normalized" / "clean.md").write_text("# sample\n", encoding="utf-8")
    (run_dir / "normalized" / "plain.txt").write_text("sample\n", encoding="utf-8")
    (run_dir / "structure" / "outline.json").write_text("[]\n", encoding="utf-8")
    (run_dir / "clauses" / "clause-001.json").write_text(
        json.dumps({"clause_id": "clause-001", "text": "sample"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "quality" / "validation-report.json").write_text(
        json.dumps({"doc_id": manifest["doc_id"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class SessionBAudit002Tests(unittest.TestCase):
    def test_policy_file_changes_publication_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "approval-rules.yaml"
            rules_path.write_text(
                yaml.dump(
                    {
                        "auto_approval": {
                            "enabled": False,
                            "conditions": [
                                {"classification_confidence": "high"},
                                {"soft_fail_count": 0},
                                {"schema_validation": "passed"},
                                {"hard_fail_count": 0},
                            ],
                        },
                        "per_asset_type": {
                            "template": {
                                "auto_approvable": True,
                                "requires_human_fields": [],
                                "default_authority_level": "preferred",
                                "default_external_safe": False,
                            }
                        },
                    },
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            original_rules_path = batch_module.APPROVAL_RULES_PATH
            batch_module.APPROVAL_RULES_PATH = rules_path
            try:
                rules = batch_module.load_approval_rules()
            finally:
                batch_module.APPROVAL_RULES_PATH = original_rules_path

            manifest = {
                "doc_id": "sample-template",
                "doc_class": "template",
                "contract_family": "ssa",
                "classification_confidence": "high",
                "authority_level": "preferred",
                "external_safe": False,
            }
            validation_report = {
                "hard_fails": [],
                "soft_fails": [],
                "schema_valid": True,
            }

            publication = batch_module.determine_publication_target(manifest, validation_report, rules)

            self.assertEqual(publication["approval_state"], "staging")
            self.assertIn("auto_approval_disabled", publication["reasons"])

    def test_staging_sync_removes_prior_approved_copy_and_writes_reason_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            approved_dir = temp_root / "approved"
            staging_dir = temp_root / "staging"
            quarantine_dir = temp_root / "quarantine"
            run_dir = temp_root / "runs" / "doc-001"

            manifest = {
                "doc_id": "doc-001",
                "doc_class": "template",
                "contract_family": "ssa",
                "approval_state": "staging",
                "authority_level": "preferred",
                "external_safe": False,
            }
            build_run_package(run_dir, manifest)

            old_approved_dir = approved_dir / "templates" / "ssa" / "doc-001"
            old_approved_dir.mkdir(parents=True, exist_ok=True)
            (old_approved_dir / "manifest.yaml").write_text("stale: true\n", encoding="utf-8")

            original_dirs = (
                batch_module.APPROVED_DIR,
                batch_module.STAGING_DIR,
                batch_module.QUARANTINE_DIR,
            )
            batch_module.APPROVED_DIR = approved_dir
            batch_module.STAGING_DIR = staging_dir
            batch_module.QUARANTINE_DIR = quarantine_dir
            try:
                destination = batch_module.sync_package_to_publication_target(
                    run_dir=run_dir,
                    manifest=manifest,
                    validation_report={"hard_fails": [], "soft_fails": ["needs review"]},
                    publication={
                        "approval_state": "staging",
                        "publication_target": "staging",
                        "reason_file": "staging-reason.json",
                        "reasons": ["auto_approval_disabled"],
                        "policy_errors": [],
                        "unmet_conditions": [],
                        "auto_approval_enabled": False,
                        "asset_auto_approvable": True,
                    },
                )
            finally:
                (
                    batch_module.APPROVED_DIR,
                    batch_module.STAGING_DIR,
                    batch_module.QUARANTINE_DIR,
                ) = original_dirs

            self.assertEqual(destination, staging_dir / "doc-001")
            self.assertFalse(old_approved_dir.exists())
            self.assertTrue((staging_dir / "doc-001" / "manifest.yaml").exists())
            reason_payload = json.loads(
                (staging_dir / "doc-001" / "staging-reason.json").read_text(encoding="utf-8")
            )
            self.assertEqual(reason_payload["approval_state"], "staging")
            self.assertIn("auto_approval_disabled", reason_payload["reasons"])


class SessionBAudit014Tests(unittest.TestCase):
    def test_supersede_rejects_self_reference(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            approved_dir = temp_root / "approved"
            indexes_dir = temp_root / "indexes"
            write_manifest(
                approved_dir / "templates" / "ssa" / "doc-001" / "manifest.yaml",
                {"doc_id": "doc-001", "status": "active"},
            )

            original_dirs = (
                supersession_module.APPROVED_DIR,
                supersession_module.INDEXES_DIR,
            )
            supersession_module.APPROVED_DIR = str(approved_dir)
            supersession_module.INDEXES_DIR = str(indexes_dir)
            try:
                result = supersession_module.supersede("doc-001", "doc-001")
            finally:
                supersession_module.APPROVED_DIR, supersession_module.INDEXES_DIR = original_dirs

            self.assertIn("cannot supersede itself", result["error"])

    def test_supersede_rejects_request_when_new_doc_already_descends_from_old(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            approved_dir = temp_root / "approved"
            indexes_dir = temp_root / "indexes"
            indexes_dir.mkdir(parents=True, exist_ok=True)

            write_manifest(
                approved_dir / "templates" / "ssa" / "doc-a" / "manifest.yaml",
                {"doc_id": "doc-a", "status": "active"},
            )
            write_manifest(
                approved_dir / "templates" / "ssa" / "doc-b" / "manifest.yaml",
                {"doc_id": "doc-b", "status": "superseded", "supersedes": "doc-a"},
            )
            write_manifest(
                approved_dir / "templates" / "ssa" / "doc-c" / "manifest.yaml",
                {"doc_id": "doc-c", "status": "active"},
            )
            (indexes_dir / "supersession.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "updated_at": "2026-03-27T00:00:00+00:00",
                        "chains": [
                            {
                                "doc_id": "doc-b",
                                "supersedes": "doc-a",
                                "superseded_by": "doc-c",
                                "status": "superseded",
                            },
                            {
                                "doc_id": "doc-c",
                                "supersedes": "doc-b",
                                "superseded_by": None,
                                "status": "active",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            original_dirs = (
                supersession_module.APPROVED_DIR,
                supersession_module.INDEXES_DIR,
            )
            supersession_module.APPROVED_DIR = str(approved_dir)
            supersession_module.INDEXES_DIR = str(indexes_dir)
            try:
                result = supersession_module.supersede("doc-a", "doc-c")
            finally:
                supersession_module.APPROVED_DIR, supersession_module.INDEXES_DIR = original_dirs

            self.assertIn("already descends from", result["error"])

    def test_diagnose_cycles_writes_report_for_existing_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            indexes_dir = temp_root / "indexes"
            indexes_dir.mkdir(parents=True, exist_ok=True)
            (indexes_dir / "supersession.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "updated_at": "2026-03-27T00:00:00+00:00",
                        "chains": [
                            {
                                "doc_id": "doc-a",
                                "supersedes": "doc-b",
                                "superseded_by": None,
                                "status": "superseded",
                            },
                            {
                                "doc_id": "doc-b",
                                "supersedes": "doc-a",
                                "superseded_by": None,
                                "status": "superseded",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            original_indexes_dir = supersession_module.INDEXES_DIR
            supersession_module.INDEXES_DIR = str(indexes_dir)
            try:
                diagnostics = supersession_module.diagnose_cycles(write_report=True)
            finally:
                supersession_module.INDEXES_DIR = original_indexes_dir

            self.assertTrue(diagnostics["has_cycles"])
            self.assertTrue(Path(diagnostics["diagnostic_report"]).exists())
            self.assertGreaterEqual(len(diagnostics["supersedes_cycles"]), 1)


if __name__ == "__main__":
    unittest.main()

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


load_state_module = load_module(
    "load_state_migration",
    ".claude/skills/pipeline-state/scripts/load-state.py",
)
save_state_module = load_module(
    "save_state_migration",
    ".claude/skills/pipeline-state/scripts/save-state.py",
)
validator_module = load_module(
    "validate_json_artifact_pipeline_state",
    ".claude/scripts/validate-json-artifact.py",
)


class PipelineStateMigrationTests(unittest.TestCase):
    def test_save_state_migrates_v1_state_and_persists_v2_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            round_dir = Path(tmpdir) / "matter-001" / "round_1"
            output_path = round_dir / "working" / "normalized" / "clean.md"
            output_path.parent.mkdir(parents=True)
            output_path.write_text("# normalized\n", encoding="utf-8")

            state_path = round_dir / "pipeline-state.json"
            v1_state = {
                "pipeline": "review",
                "matter_id": "matter-001",
                "round": 1,
                "last_completed_step": 1,
                "review_mode": "moderate",
                "step_artifacts": {
                    "step_1": {
                        "name": "Normalize",
                        "status": "completed",
                        "output": "working/normalized/clean.md",
                        "completed_at": "2026-03-27T00:00:00+00:00",
                    }
                },
                "started_at": "2026-03-27T00:00:00+00:00",
                "updated_at": "2026-03-27T00:00:00+00:00",
            }
            state_path.write_text(
                json.dumps(v1_state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = save_state_module.save_state(
                state_path=str(state_path),
                pipeline="review",
                matter_id="matter-001",
                round_num=1,
                step=2,
                step_name="Clause Mapping",
                status="completed",
                output="working/docx-clause-map.json",
                review_mode="moderate",
                session_id="review-session-001",
                validation={
                    "coverage": 0.94,
                    "coverage_status": "proceed",
                    "unmapped_clause_ids": [],
                },
                metrics={
                    "reference_full_load_count": 0,
                    "retrieval_tokens_estimated": 800,
                    "hydrated_candidate_count": 2,
                },
            )

            self.assertTrue(result["success"], result)
            self.assertEqual(result["schema_version"], 2)
            self.assertEqual(result["session_id"], "review-session-001")

            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], 2)
            self.assertEqual(saved["session_id"], "review-session-001")
            self.assertEqual(saved["metrics"]["retrieval_tokens_estimated"], 800)
            self.assertEqual(
                saved["step_artifacts"]["step_2"]["validation"]["coverage_status"],
                "proceed",
            )
            self.assertEqual(saved["step_artifacts"]["step_1"]["name"], "Normalize")

            schema_path = REPO_ROOT / ".claude" / "schemas" / "pipeline-state.schema.json"
            errors = validator_module.validate_artifact(schema_path, state_path)
            self.assertEqual(errors, [])

    def test_load_state_migrates_v1_state_in_memory_for_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "round_1" / "pipeline-state.json"
            state_path.parent.mkdir()
            state_path.write_text(
                json.dumps(
                    {
                        "pipeline": "review",
                        "matter_id": "matter-002",
                        "round": 1,
                        "last_completed_step": 0,
                        "step_artifacts": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = load_state_module.load_state(str(state_path))

            self.assertTrue(result["exists"])
            self.assertTrue(result["migration"]["migrated"])
            self.assertIsNone(result["migration"]["from_schema_version"])
            self.assertEqual(result["schema_version"], 2)
            self.assertEqual(result["state"]["schema_version"], 2)
            self.assertEqual(result["state"]["metrics"], {})
            self.assertTrue(result["session_id"].startswith("review-matter-002-round-1-"))

    def write_reference_bundle(self, root: Path) -> None:
        refs_dir = root / ".claude" / "skills" / "review-domain-knowledge" / "references"
        refs_dir.mkdir(parents=True)
        (refs_dir / "review-guide.md").write_text(
            "# Review Guide\n\n## Risk Grading Criteria\n\nCriteria.\n",
            encoding="utf-8",
        )
        (refs_dir / "audience-firewall.md").write_text(
            "# Audience Firewall\n\n## What MUST NOT appear\n\nInternal strategy.\n",
            encoding="utf-8",
        )

    @unittest.skipIf(shutil.which("jq") is None, "jq is required by the loader script")
    def test_reference_loader_writes_to_explicit_session_trace_dirs(self):
        script = REPO_ROOT / ".claude" / "scripts" / "load-domain-references.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            self.write_reference_bundle(temp_root)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(temp_root)}

            for session_id in ["review-session-a", "review-session-b"]:
                trace_dir = temp_root / "matter" / "working" / "traces" / session_id
                result = subprocess.run(
                    [
                        "bash",
                        str(script),
                        "review",
                        "--mode=digest",
                        f"--session-id={session_id}",
                        f"--trace-dir={trace_dir}",
                    ],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"SESSION_ID: {session_id}", result.stdout)

                trace = json.loads((trace_dir / "loaded.json").read_text(encoding="utf-8"))
                self.assertEqual(trace["session_id"], session_id)
                self.assertEqual(trace["loader_mode"], "digest")

            trace_a = temp_root / "matter" / "working" / "traces" / "review-session-a" / "loaded.json"
            trace_b = temp_root / "matter" / "working" / "traces" / "review-session-b" / "loaded.json"
            self.assertTrue(trace_a.exists())
            self.assertTrue(trace_b.exists())
            self.assertNotEqual(trace_a, trace_b)

    @unittest.skipIf(shutil.which("jq") is None, "jq is required by the loader script")
    def test_reference_loader_default_trace_uses_workspace_runs_with_legacy_fallback(self):
        script = REPO_ROOT / ".claude" / "scripts" / "load-domain-references.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            self.write_reference_bundle(temp_root)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(temp_root)}

            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "review",
                    "--mode=digest",
                    "--session-id=default-workspace",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            expected = temp_root / "contract-review" / "workspace" / "runs" / "sessions" / "default-workspace" / "loaded.json"
            self.assertTrue(expected.exists())
            self.assertIn(f"TRACE: {expected}", result.stdout)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            self.write_reference_bundle(temp_root)
            legacy_runs = temp_root / "contract-review" / "library" / "runs"
            legacy_runs.mkdir(parents=True)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(temp_root)}

            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "review",
                    "--mode=digest",
                    "--session-id=legacy-fallback",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            expected = legacy_runs / "sessions" / "legacy-fallback" / "loaded.json"
            self.assertTrue(expected.exists())
            self.assertIn(f"TRACE: {expected}", result.stdout)


if __name__ == "__main__":
    unittest.main()

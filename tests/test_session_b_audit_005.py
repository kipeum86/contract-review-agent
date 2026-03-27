import importlib.util
import json
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
    "load_state_module",
    ".claude/skills/pipeline-state/scripts/load-state.py",
)
save_state_module = load_module(
    "save_state_module",
    ".claude/skills/pipeline-state/scripts/save-state.py",
)


class SessionBAudit005Tests(unittest.TestCase):
    def test_load_state_rewinds_to_first_missing_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            round_dir = Path(tmpdir) / "matter-001" / "round_1"
            state_path = round_dir / "pipeline-state.json"
            existing_output = round_dir / "working" / "normalized" / "clean.md"
            existing_output.parent.mkdir(parents=True, exist_ok=True)
            existing_output.write_text("# normalized\n", encoding="utf-8")

            state = {
                "pipeline": "review",
                "last_completed_step": 3,
                "step_artifacts": {
                    "step_1": {
                        "name": "Normalize",
                        "status": "completed",
                        "output": "working/normalized/clean.md",
                    },
                    "step_2": {
                        "name": "Clause Segmentation",
                        "status": "completed",
                        "output": "working/clauses/",
                    },
                    "step_3": {
                        "name": "Classify Clauses",
                        "status": "completed",
                        "output": "working/classification.json",
                    },
                },
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            result = load_state_module.load_state(str(state_path))

            self.assertEqual(result["declared_resume_from"], 4)
            self.assertEqual(result["resume_from"], 2)
            self.assertEqual(result["verified_through_step"], 1)
            self.assertFalse(result["is_complete"])
            self.assertEqual(
                result["artifact_verification"]["earliest_invalid_step"],
                2,
            )
            step_2_check = result["artifact_verification"]["checks"][1]
            self.assertEqual(
                step_2_check["resolved_output"],
                str(round_dir / "working" / "clauses"),
            )

    def test_load_state_treats_empty_directory_as_invalid_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            round_dir = Path(tmpdir) / "round_1"
            empty_dir = round_dir / "working" / "clauses"
            empty_dir.mkdir(parents=True, exist_ok=True)
            state_path = round_dir / "pipeline-state.json"
            state = {
                "pipeline": "review",
                "last_completed_step": 1,
                "step_artifacts": {
                    "step_1": {
                        "name": "Clause Segmentation",
                        "status": "completed",
                        "output": "working/clauses",
                    }
                },
            }
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            result = load_state_module.load_state(str(state_path))

            self.assertEqual(result["resume_from"], 1)
            self.assertEqual(
                result["artifact_verification"]["checks"][-1]["reason"],
                "empty_directory",
            )

    def test_load_state_flags_restart_when_majority_of_checked_artifacts_are_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            round_dir = Path(tmpdir) / "round_1"
            existing_file = round_dir / "working" / "step-1.txt"
            existing_file.parent.mkdir(parents=True, exist_ok=True)
            existing_file.write_text("ok\n", encoding="utf-8")
            state_path = round_dir / "pipeline-state.json"
            state = {
                "pipeline": "review",
                "last_completed_step": 4,
                "step_artifacts": {
                    "step_1": {
                        "name": "Step 1",
                        "status": "completed",
                        "output": "working/step-1.txt",
                    },
                    "step_2": {
                        "name": "Step 2",
                        "status": "completed",
                        "output": "working/missing-2.txt",
                    },
                    "step_3": {
                        "name": "Step 3",
                        "status": "completed",
                        "output": "working/missing-3.txt",
                    },
                    "step_4": {
                        "name": "Step 4",
                        "status": "completed",
                        "output": "working/missing-4.txt",
                    },
                },
            }
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

            result = load_state_module.load_state(str(state_path))

            self.assertEqual(result["resume_from"], 2)
            self.assertTrue(result["artifact_verification"]["restart_recommended"])
            self.assertEqual(result["artifact_verification"]["checked_steps"], 4)
            self.assertEqual(result["artifact_verification"]["failed_checks"], 3)

    def test_save_state_preserves_existing_file_when_atomic_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "pipeline-state.json"
            original_state = {
                "pipeline": "review",
                "matter_id": "matter-001",
                "round": 1,
                "last_completed_step": 1,
                "review_mode": "standard",
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
                json.dumps(original_state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            original_replace = save_state_module.os.replace

            def failing_replace(src, dst):
                raise OSError("simulated replace failure")

            save_state_module.os.replace = failing_replace
            try:
                result = save_state_module.save_state(
                    state_path=str(state_path),
                    pipeline="review",
                    matter_id="matter-001",
                    round_num=1,
                    step=2,
                    step_name="Segment",
                    status="completed",
                    output="working/clauses",
                    review_mode="standard",
                )
            finally:
                save_state_module.os.replace = original_replace

            self.assertFalse(result["success"])
            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8")),
                original_state,
            )
            temp_files = list(state_path.parent.glob(".pipeline-state.json.*.tmp"))
            self.assertEqual(temp_files, [])


if __name__ == "__main__":
    unittest.main()

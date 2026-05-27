import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "pretooluse-guard.py"


def run_hook(payload: dict | str, *, use_stdin: bool = False) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PROJECT_DIR"] = str(REPO_ROOT)
    env.pop("TOOL_INPUT", None)

    input_text = None
    if isinstance(payload, str):
        payload_text = payload
    else:
        payload_text = json.dumps(payload)

    if use_stdin:
        input_text = payload_text
    else:
        env["TOOL_INPUT"] = payload_text

    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=REPO_ROOT,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


class ClaudePreToolUseGuardTests(unittest.TestCase):
    def test_allowed_repo_write_path_passes(self):
        result = run_hook({"file_path": "contract-review/matters/demo/round_1/state.json"})

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_repo_external_write_path_blocks(self):
        result = run_hook({"file_path": "/tmp/outside-contract-review-agent.txt"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("outside allowed directories", result.stderr)

    def test_direct_approved_template_write_blocks(self):
        result = run_hook({"command": "cp seed.md contract-review/library/approved/templates/demo/clean.md"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("Direct Bash writes", result.stderr)

    def test_direct_approved_redirect_write_blocks(self):
        result = run_hook({"command": "printf x > contract-review/library/approved/templates/demo/clean.md"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("Direct Bash writes", result.stderr)

    def test_allowed_publisher_command_passes(self):
        result = run_hook(
            {
                "command": (
                    "python3 .claude/skills/index-manager/scripts/build-index.py "
                    "contract-review/library/approved/templates"
                )
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_general_bash_command_fast_path_passes(self):
        result = run_hook({"command": "python3 -m pytest -q"})

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_json_passes(self):
        result = run_hook("{not-json")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stdin_payload_passes(self):
        result = run_hook({"file_path": ".claude/hooks/pretooluse-guard.py"}, use_stdin=True)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

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

        self.assertEqual(result.returncode, 2)
        self.assertIn("outside allowed directories", result.stderr)

    def test_direct_approved_template_write_blocks(self):
        result = run_hook({"command": "cp seed.md contract-review/library/approved/templates/demo/clean.md"})

        self.assertEqual(result.returncode, 2)
        self.assertIn("Direct Bash writes", result.stderr)

    def test_direct_approved_redirect_write_blocks(self):
        result = run_hook({"command": "printf x > contract-review/library/approved/templates/demo/clean.md"})

        self.assertEqual(result.returncode, 2)
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

    def test_nested_tool_input_payload_blocks(self):
        # Claude Code sends {"tool_name": ..., "tool_input": {...}} on stdin.
        result = run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/outside-contract-review-agent.txt"},
            },
            use_stdin=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside allowed directories", result.stderr)

    def test_block_exit_code_is_2(self):
        # Claude Code only blocks a tool call on exit code 2; exit 1 is advisory.
        result = run_hook({"file_path": "/tmp/outside-contract-review-agent.txt"})
        self.assertEqual(result.returncode, 2)

    def test_write_tool_into_approved_blocks(self):
        result = run_hook(
            {"file_path": "contract-review/library/approved/templates/nda/x/clean.md"}
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("approved", result.stderr)

    def test_write_tool_into_matters_still_allowed(self):
        result = run_hook(
            {"file_path": "contract-review/workspace/matters/demo/round_1/state.json"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_redirect_without_space_blocks(self):
        result = run_hook(
            {"command": "echo x >contract-review/library/approved/templates/demo/clean.md"}
        )
        self.assertEqual(result.returncode, 2)


class ClaudeHookRegistrationTests(unittest.TestCase):
    """Audit A-1: hooks must actually be registered in a tracked settings file."""

    SETTINGS = REPO_ROOT / ".claude" / "settings.json"

    def load_settings(self) -> dict:
        self.assertTrue(
            self.SETTINGS.exists(),
            ".claude/settings.json must be tracked so cloned repos get hooks",
        )
        return json.loads(self.SETTINGS.read_text(encoding="utf-8"))

    def test_tracked_settings_contains_hooks_only(self):
        self.assertEqual(set(self.load_settings()), {"hooks"})

    def test_settings_json_is_tracked_by_git(self):
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".claude/settings.json"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, "settings.json is not git-tracked")

    def test_user_prompt_submit_hook_registered(self):
        settings = self.load_settings()
        entries = settings.get("hooks", {}).get("UserPromptSubmit", [])
        commands = [
            hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
        ]
        self.assertTrue(
            any("inject-domain-references.sh" in cmd for cmd in commands),
            f"UserPromptSubmit hook missing: {commands}",
        )

    def test_pre_tool_use_guard_registered(self):
        settings = self.load_settings()
        entries = settings.get("hooks", {}).get("PreToolUse", [])
        commands = [
            hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
        ]
        self.assertTrue(
            any("pretooluse-guard.py" in cmd for cmd in commands),
            f"PreToolUse guard missing: {commands}",
        )

    def test_registered_hook_scripts_exist_and_executable(self):
        for rel in (
            ".claude/hooks/inject-domain-references.sh",
            ".claude/hooks/pretooluse-guard.py",
        ):
            path = REPO_ROOT / rel
            self.assertTrue(path.exists(), rel)


if __name__ == "__main__":
    unittest.main()

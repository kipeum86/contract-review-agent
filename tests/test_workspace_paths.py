import subprocess
import tempfile
import unittest
from shlex import quote
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / ".claude" / "scripts" / "workspace-paths.sh"
HELPER_SH = quote(str(HELPER))


def run_bash(script: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class WorkspacePathHelperTests(unittest.TestCase):
    def test_defaults_prefer_unified_workspace_and_keep_legacy_search_paths(self):
        result = run_bash(
            f"""
            set -euo pipefail
            source {HELPER_SH}
            printf '%s\\n' "$CRA_INPUT_DIR"
            printf '%s\\n' "$CRA_OUTPUT_DIR"
            printf '%s\\n' "$CRA_MATTERS_DIR"
            printf '%s\\n' "$CRA_RUNS_DIR"
            printf '%s\\n' "$CRA_INPUT_DIRS"
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines[0], str(REPO_ROOT / "contract-review" / "workspace" / "input"))
        self.assertEqual(lines[1], str(REPO_ROOT / "contract-review" / "workspace" / "output"))
        self.assertEqual(lines[2], str(REPO_ROOT / "contract-review" / "workspace" / "matters"))
        self.assertEqual(lines[3], str(REPO_ROOT / "contract-review" / "workspace" / "runs"))
        self.assertIn(str(REPO_ROOT / "input"), lines[4])

    def test_explicit_environment_values_are_preserved(self):
        result = run_bash(
            f"""
            set -euo pipefail
            export CRA_INPUT_DIR=/tmp/custom-input
            export CRA_OUTPUT_DIR=/tmp/custom-output
            source {HELPER_SH}
            printf '%s\\n' "$CRA_INPUT_DIR"
            printf '%s\\n' "$CRA_OUTPUT_DIR"
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), ["/tmp/custom-input", "/tmp/custom-output"])

    def test_falls_back_to_legacy_when_workspace_is_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "input").mkdir()
            (root / "output").mkdir()
            (root / "logs").mkdir()
            (root / "contract-review" / "matters").mkdir(parents=True)
            (root / "contract-review" / "library" / "runs").mkdir(parents=True)

            result = run_bash(
                f"""
                set -euo pipefail
                export CRA_PROJECT_ROOT={quote(str(root))}
                source {HELPER_SH}
                printf '%s\\n' "$CRA_INPUT_DIR"
                printf '%s\\n' "$CRA_OUTPUT_DIR"
                printf '%s\\n' "$CRA_MATTERS_DIR"
                printf '%s\\n' "$CRA_RUNS_DIR"
                """,
                cwd=root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.strip().splitlines(),
                [
                    str(root / "input"),
                    str(root / "output"),
                    str(root / "contract-review" / "matters"),
                    str(root / "contract-review" / "library" / "runs"),
                ],
            )


if __name__ == "__main__":
    unittest.main()

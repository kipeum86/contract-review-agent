"""Test bootstrap for fresh clones (audit C-1).

Local-only state (user policies, generated indexes) is gitignored by design.
Tests that exercise the library pipeline need that state to exist, so we
materialize it idempotently before collection:

1. Copy any missing policy YAML from policies.default/ into policies/
   (mirrors the CLAUDE.md "Policy Initialization" contract).
2. Build the library index from the tracked seed templates when absent.

Both steps are no-ops on an already-initialized developer environment.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = REPO_ROOT / "contract-review" / "library"
POLICY_FILES = (
    "approval-rules.yaml",
    "clause-taxonomy.yaml",
    "contract-families.yaml",
    "metadata-schema.yaml",
    "retrieval-priority.yaml",
    "review-mode.yaml",
    "seed-calibration-policy.yaml",
)


def _init_policies() -> None:
    defaults_dir = LIBRARY_DIR / "policies.default"
    target_dir = LIBRARY_DIR / "policies"
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in POLICY_FILES:
        source = defaults_dir / name
        target = target_dir / name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def _build_index_if_missing() -> None:
    indexes_dir = LIBRARY_DIR / "indexes"
    if (indexes_dir / "clauses.json").exists():
        return
    build_script = (
        REPO_ROOT / ".claude" / "skills" / "index-manager" / "scripts" / "build-index.py"
    )
    result = subprocess.run(
        [sys.executable, str(build_script), "rebuild"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"index rebuild failed during test bootstrap:\n{result.stdout}\n{result.stderr}"
        )


def pytest_configure(config):
    _init_policies()
    _build_index_if_missing()

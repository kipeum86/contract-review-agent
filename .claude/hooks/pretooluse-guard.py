#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path


APPROVED_MARKERS = (
    "contract-review/library/approved",
    "approved/templates",
    "approved/precedents",
    "approved/playbooks",
    "approved/comment-bank",
)

ALLOWED_PUBLISHERS = (
    "scripts/batch_classify_and_publish.py",
    ".claude/skills/index-manager/scripts/supersession.py",
    ".claude/skills/index-manager/scripts/build-index.py",
)

DIRECT_WRITE_RE = re.compile(r"\b(cp|mv|rsync|install|ditto|mkdir|tee)\b|(?:^|\s)(>|>>)(?=\s)")

# Claude Code blocks the tool call only on exit code 2 (exit 1 is advisory).
BLOCK_EXIT = 2


def read_payload() -> dict:
    raw = os.environ.get("TOOL_INPUT")
    if raw is None:
        try:
            raw = "" if sys.stdin.isatty() else sys.stdin.read()
        except Exception:
            raw = ""

    try:
        data = json.loads(raw or "{}")
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    # Claude Code PreToolUse hooks deliver {"tool_name": ..., "tool_input": {...}}.
    # Unwrap tool_input when present; keep flat payloads working for tests/CLI.
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        return tool_input
    return data


def project_root() -> Path:
    root = os.environ.get("PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(root).expanduser().resolve()


def resolve_candidate(path_value: str, root: Path) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def is_same_or_inside(candidate: Path, allowed_path: Path) -> bool:
    allowed_path = allowed_path.resolve()
    return candidate == allowed_path or allowed_path in candidate.parents


def allowed_write_paths(root: Path) -> tuple[Path, ...]:
    return (
        root / "contract-review",
        root / ".claude",
        root / "docs",
        root / "_private",
        root / "CLAUDE.md",
        root / "package.json",
        root / "package-lock.json",
        root / "node_modules",
    )


def check_file_path(data: dict, root: Path) -> int:
    file_path = data.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return 0

    abs_path = resolve_candidate(file_path, root)
    if any(is_same_or_inside(abs_path, allowed) for allowed in allowed_write_paths(root)):
        return 0

    print(f"BLOCKED: Write to {abs_path} is outside allowed directories", file=sys.stderr)
    return BLOCK_EXIT


def check_command(data: dict) -> int:
    command = data.get("command") or data.get("cmd") or ""
    if not isinstance(command, str) or not command:
        return 0

    normalized_command = command.lower()
    if not any(marker in normalized_command for marker in APPROVED_MARKERS):
        return 0

    if any(publisher in normalized_command for publisher in ALLOWED_PUBLISHERS):
        return 0

    if DIRECT_WRITE_RE.search(command):
        print(
            "BLOCKED: Direct Bash writes to contract-review/library/approved are disallowed. "
            "Use the publish workflow or index-manager service.",
            file=sys.stderr,
        )
        return BLOCK_EXIT

    return 0


def main() -> int:
    data = read_payload()
    root = project_root()

    file_result = check_file_path(data, root)
    if file_result:
        return file_result

    return check_command(data)


if __name__ == "__main__":
    sys.exit(main())

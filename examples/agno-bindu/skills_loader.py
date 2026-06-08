"""Load the upstream project's Claude Code skills into agno, in place.

`contract-review-agent` is a Claude Code application: its capabilities live in
`.claude/skills/<name>/SKILL.md` (instructions), `references/` (methodology docs),
and `scripts/` (deterministic helpers). agno can consume exactly this layout via its
Skills feature, with one snag: most of the upstream `SKILL.md` files have no YAML
frontmatter, which agno's default `LocalSkills` loader rejects.

`ClaudeCodeSkills` bridges that gap without touching the upstream files: it loads
them with validation off (the folder name becomes the skill name) and backfills the
missing one-line `description`. `source_path` points straight at the upstream skill
folders, so their real `references/` and `scripts/` are read and executed in place.
Nothing is copied or modified.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from agno.skills import LocalSkills, Skills

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    """Root of the contract-review-agent checkout.

    By default this example lives at ``<repo>/examples/agno-bindu/``, so the repo
    root is two levels up. Override with ``CONTRACT_REVIEW_REPO`` to run it from
    elsewhere.
    """
    override = os.getenv("CONTRACT_REVIEW_REPO")
    if override:
        return Path(override).expanduser().resolve()
    return HERE.parents[1]


def skills_dir() -> Path:
    return repo_root() / ".claude" / "skills"


def policies_dir() -> Path:
    return repo_root() / "contract-review" / "library" / "policies.default"


# The review-relevant, text-native skills. The upstream ships more skills
# (doc-parser, docx-redliner, report-compiler, index-manager, metadata-validator,
# pipeline-state, ingest) that drive its full *local* DOCX pipeline; those need files
# on disk / Node / the local library and are out of scope for this stateless,
# text-in A2A surface.
DEFAULT_SKILLS = ("review-domain-knowledge", "clause-segmenter")


def _first_paragraph(skill_md: Path) -> str:
    """First non-heading, non-frontmatter line of a SKILL.md (its summary)."""
    try:
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("---"):
                continue
            return stripped
    except OSError:
        pass
    return ""


class ClaudeCodeSkills(LocalSkills):
    """`LocalSkills` adapted to frontmatter-less Anthropic-style `.claude/skills/`."""

    def __init__(self, path: str | os.PathLike[str], only: Iterable[str] | None = None):
        super().__init__(str(path), validate=False)
        self._only = set(only) if only is not None else None

    def load(self):
        skills = []
        for skill in super().load():
            if self._only is not None and skill.name not in self._only:
                continue
            if not skill.description:
                skill.description = _first_paragraph(Path(skill.source_path) / "SKILL.md")
            skills.append(skill)
        return skills


def build_skills(only: Iterable[str] | None = DEFAULT_SKILLS) -> Skills:
    sdir = skills_dir()
    if not sdir.exists():
        raise RuntimeError(
            f"Upstream skills directory not found: {sdir}\n"
            "Run this example from inside the contract-review-agent repo, or set "
            "CONTRACT_REVIEW_REPO to the repo root."
        )
    return Skills(loaders=[ClaudeCodeSkills(sdir, only=only)])


_POLICY_FILES = {
    "review-mode",
    "contract-families",
    "clause-taxonomy",
    "approval-rules",
    "retrieval-priority",
    "metadata-schema",
}


def load_policy(name: str) -> str:
    """Return an upstream review-policy YAML by name.

    These files define the house review configuration: the strict/moderate/loose
    review modes and their redline/comment scopes (`review-mode`), the 29 supported
    contract families (`contract-families`), and the clause taxonomy used for
    classification (`clause-taxonomy`). Read them to ground a review in the project's
    own configuration rather than guessing.

    Args:
        name: policy stem — one of: review-mode, contract-families, clause-taxonomy,
            approval-rules, retrieval-priority, metadata-schema.

    Returns:
        The raw YAML text, or a JSON error string if the name is not recognized.
    """
    key = name.strip().removesuffix(".yaml")
    if key not in _POLICY_FILES:
        return json.dumps({"error": f"Unknown policy '{name}'", "available": sorted(_POLICY_FILES)})
    path = policies_dir() / f"{key}.yaml"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return json.dumps({"error": f"Could not read policy '{key}': {exc}"})

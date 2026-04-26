#!/usr/bin/env python3
"""Validate source-registry.json integrity and freshness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "source_id",
    "title",
    "jurisdiction",
    "source_type",
    "authority_level",
    "last_checked",
    "path",
    "sha256",
]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None


def source_body_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            text = parts[2].lstrip("\n")
    return hashlib.sha256(text.rstrip().encode("utf-8")).hexdigest()


def validate_registry(registry_path: str, library_root: str | None = None,
                      stale_days: int = 365) -> dict[str, Any]:
    path = Path(registry_path)
    root = Path(library_root) if library_root else path.parents[1]
    errors = []
    warnings = []

    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "success": False,
            "registry_path": str(path),
            "errors": [str(exc)],
            "warnings": [],
        }

    sources = registry.get("sources")
    if not isinstance(sources, list):
        return {
            "success": False,
            "registry_path": str(path),
            "errors": ["$.sources must be an array"],
            "warnings": [],
        }

    seen = set()
    today = date.today()
    stale_source_ids = []

    for index, entry in enumerate(sources):
        if not isinstance(entry, dict):
            errors.append(f"$.sources[{index}] must be an object")
            continue

        source_id = entry.get("source_id")
        if source_id in seen:
            errors.append(f"duplicate source_id: {source_id}")
        if source_id:
            seen.add(source_id)

        for field in REQUIRED_FIELDS:
            if entry.get(field) in (None, ""):
                errors.append(f"$.sources[{index}] missing required field: {field}")

        relative_path = entry.get("path")
        if relative_path:
            source_path = root / relative_path
            if not source_path.exists():
                errors.append(f"{source_id}: path does not exist: {relative_path}")
            else:
                actual_sha = source_body_sha256(source_path)
                if entry.get("sha256") and entry["sha256"] != actual_sha:
                    errors.append(f"{source_id}: sha256 mismatch")

        checked = parse_date(entry.get("last_checked"))
        if checked is None:
            errors.append(f"{source_id}: invalid last_checked")
        elif (today - checked).days > stale_days:
            stale_source_ids.append(source_id)
            warnings.append(f"{source_id}: stale source, last_checked={entry.get('last_checked')}")

    return {
        "success": not errors,
        "registry_path": str(path),
        "source_count": len(sources),
        "stale_source_count": len(stale_source_ids),
        "stale_source_ids": stale_source_ids,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate source-registry.json.")
    parser.add_argument("registry_path")
    parser.add_argument("--library-root")
    parser.add_argument("--stale-days", type=int, default=365)
    args = parser.parse_args()

    result = validate_registry(args.registry_path, args.library_root, args.stale_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

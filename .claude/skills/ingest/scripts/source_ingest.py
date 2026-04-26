#!/usr/bin/env python3
"""Ingest reference sources into the local source registry."""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
LIBRARY_ROOT = REPO_ROOT / "contract-review" / "library"
REGISTRY_RELATIVE = Path("sources") / "source-registry.json"
APPROVED_RELATIVE = Path("sources") / "approved"


def load_normalize_module():
    module_path = REPO_ROOT / ".claude" / "skills" / "doc-parser" / "scripts" / "normalize.py"
    spec = importlib.util.spec_from_file_location("source_ingest_normalize", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Unable to load normalize module: {module_path}")
    spec.loader.exec_module(module)
    return module


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^0-9a-z가-힣_.-]+", "", value)
    value = re.sub(r"-{2,}", "-", value).strip("-._")
    return value or "source"


def first_heading(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return fallback


def extract_statutes(text: str) -> list[str]:
    matches = re.findall(r"(?:[가-힣A-Za-z ]+법)?[ \t]*제[ \t]*\d+[ \t]*조(?:의[ \t]*\d+)?", text)
    normalized = [re.sub(r"\s+", " ", match).strip() for match in matches]
    return sorted(set(item for item in normalized if item))


def infer_contract_families(text: str) -> list[str]:
    haystack = text.lower()
    mapping = {
        "nda": ["confidential", "비밀", "non-disclosure", "nda"],
        "ssa": ["subscription", "신주", "주식인수", "share subscription"],
        "sha": ["shareholders", "주주간", "shareholder"],
        "spa": ["share purchase", "주식매매", "양수도"],
        "services": ["service", "용역", "위탁"],
        "license": ["license", "라이선스", "사용권"],
    }
    families = []
    for family, needles in mapping.items():
        if any(needle in haystack for needle in needles):
            families.append(family)
    return families


def load_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.exists():
        return {"schema_version": 1, "sources": []}
    return json.loads(registry_path.read_text(encoding="utf-8"))


def write_registry(registry_path: Path, registry: dict[str, Any]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def convert_to_markdown(input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix == ".md":
        return input_path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".txt":
        return input_path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        normalize_module = load_normalize_module()
        return normalize_module.strip_html_tags(
            input_path.read_text(encoding="utf-8", errors="replace")
        )
    if suffix == ".docx":
        normalize_module = load_normalize_module()
        text = normalize_module.extract_docx_text(str(input_path))
        if text:
            return text
        raise ValueError("failed_to_extract_docx_text")
    if suffix == ".pdf":
        normalize_module = load_normalize_module()
        text = normalize_module.extract_pdf_text(str(input_path))
        if text:
            return text
        raise ValueError("failed_to_extract_pdf_text")
    raise ValueError(f"unsupported_extension:{suffix}")


def build_frontmatter(entry: dict[str, Any]) -> str:
    lines = ["---"]
    for key in [
        "source_id",
        "title",
        "jurisdiction",
        "source_type",
        "authority_level",
        "effective_date",
        "last_checked",
        "original_format",
        "ingested_at",
        "sha256",
    ]:
        value = entry.get(key)
        if value is None:
            value = ""
        lines.append(f'{key}: "{str(value).replace(chr(34), chr(92) + chr(34))}"')
    for key in ["keywords", "relevant_statutes", "contract_families_relevant"]:
        values = entry.get(key) or []
        rendered = ", ".join(json.dumps(value, ensure_ascii=False) for value in values)
        lines.append(f"{key}: [{rendered}]")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def ingest_source(
    input_path: str,
    library_root: str | None = None,
    source_id: str | None = None,
    title: str | None = None,
    jurisdiction: str = "UNSPECIFIED",
    source_type: str = "other",
    authority_level: str = "reference",
    effective_date: str | None = None,
    last_checked: str | None = None,
    move_processed: bool = False,
) -> dict[str, Any]:
    input_file = Path(input_path)
    root = Path(library_root) if library_root else LIBRARY_ROOT
    registry_path = root / REGISTRY_RELATIVE
    approved_dir = root / APPROVED_RELATIVE

    if not input_file.exists():
        return {"success": False, "error": f"file_not_found:{input_path}"}

    markdown_text = convert_to_markdown(input_file)
    extracted_title = title or first_heading(markdown_text, input_file.stem)
    slug = slugify(extracted_title)
    source_id = source_id or f"{slug}-{date.today().isoformat()}"
    source_id = slugify(source_id)

    registry = load_registry(registry_path)
    sources = registry.setdefault("sources", [])
    if any(entry.get("source_id") == source_id for entry in sources):
        return {
            "success": False,
            "error": "duplicate_source_id",
            "source_id": source_id,
            "registry_path": str(registry_path),
        }

    approved_dir.mkdir(parents=True, exist_ok=True)
    destination = approved_dir / f"{source_id}.md"
    if destination.exists():
        return {"success": False, "error": "destination_exists", "path": str(destination)}

    ingested_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "source_id": source_id,
        "title": extracted_title,
        "jurisdiction": jurisdiction,
        "source_type": source_type,
        "authority_level": authority_level,
        "effective_date": effective_date or "",
        "last_checked": last_checked or date.today().isoformat(),
        "path": str(destination.relative_to(root)),
        "sha256": sha256_text(markdown_text.rstrip()),
        "original_format": input_file.suffix.lower().lstrip(".") or "txt",
        "ingested_at": ingested_at,
        "keywords": [],
        "relevant_statutes": extract_statutes(markdown_text),
        "contract_families_relevant": infer_contract_families(markdown_text),
        "source_file": str(input_file),
    }

    destination.write_text(build_frontmatter(entry) + markdown_text.rstrip() + "\n", encoding="utf-8")
    sources.append(entry)
    sources.sort(key=lambda item: item.get("source_id", ""))
    write_registry(registry_path, registry)

    processed_path = None
    if move_processed:
        processed_dir = root / "inbox" / "_processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        processed_path = processed_dir / input_file.name
        shutil.move(str(input_file), str(processed_path))

    return {
        "success": True,
        "source_id": source_id,
        "output_path": str(destination),
        "registry_path": str(registry_path),
        "processed_path": str(processed_path) if processed_path else None,
        "entry": entry,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a reference source into source-registry.json.")
    parser.add_argument("input_path")
    parser.add_argument("--library-root")
    parser.add_argument("--source-id")
    parser.add_argument("--title")
    parser.add_argument("--jurisdiction", default="UNSPECIFIED")
    parser.add_argument("--source-type", default="other")
    parser.add_argument("--authority-level", default="reference")
    parser.add_argument("--effective-date")
    parser.add_argument("--last-checked")
    parser.add_argument("--move-processed", action="store_true")
    args = parser.parse_args()

    result = ingest_source(
        input_path=args.input_path,
        library_root=args.library_root,
        source_id=args.source_id,
        title=args.title,
        jurisdiction=args.jurisdiction,
        source_type=args.source_type,
        authority_level=args.authority_level,
        effective_date=args.effective_date,
        last_checked=args.last_checked,
        move_processed=args.move_processed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

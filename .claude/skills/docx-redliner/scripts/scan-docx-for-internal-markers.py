#!/usr/bin/env python3
"""Scan an external-clean DOCX for internal-only markers and strategy terms."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_POLICY_PATH = REPO_ROOT / ".claude" / "policies" / "external-clean-policy.yaml"

TEXT_TAGS = {"t", "delText", "instrText"}
STORY_PART_RE = re.compile(
    r"^word/(?:document|comments|threadedComments|header\d+|footer\d+|footnotes|endnotes)\.xml$"
)


def local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def load_policy(policy_path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    with policy_path.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle) or {}
    policy.setdefault("blocked_patterns", [])
    return policy


def compile_patterns(policy: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = []
    for entry in policy.get("blocked_patterns", []):
        try:
            compiled = re.compile(entry["pattern"], re.IGNORECASE)
        except (KeyError, re.error):
            continue
        patterns.append({**entry, "compiled": compiled})
    return patterns


def xml_text(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""

    parts = []
    for node in root.iter():
        if local_name(node.tag) in TEXT_TAGS and node.text:
            parts.append(node.text)
    return " ".join(part.strip() for part in parts if part.strip())


def scan_text(text: str, part_name: str, patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    violations = []
    for pattern in patterns:
        for match in pattern["compiled"].finditer(text):
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            violations.append({
                "part": part_name,
                "pattern_id": pattern.get("id"),
                "category": pattern.get("category"),
                "reason": pattern.get("reason"),
                "matched_text": match.group(0),
                "snippet": text[start:end],
            })
    return violations


def scan_unpacked_docx(source_dir: str, policy_path: str | None = None) -> dict[str, Any]:
    policy = load_policy(Path(policy_path) if policy_path else DEFAULT_POLICY_PATH)
    patterns = compile_patterns(policy)
    violations = []
    scanned_parts = 0

    for root, _, filenames in os.walk(source_dir):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            part_name = os.path.relpath(full_path, source_dir).replace(os.sep, "/")
            if not STORY_PART_RE.match(part_name):
                continue
            try:
                text = xml_text(Path(full_path).read_bytes())
            except OSError:
                continue
            scanned_parts += 1
            violations.extend(scan_text(text, part_name, patterns))

    return {
        "success": not violations,
        "status": "pass" if not violations else "fail",
        "policy_version": policy.get("version"),
        "source": source_dir,
        "scanned_parts": scanned_parts,
        "violation_count": len(violations),
        "violations": violations,
    }


def scan_docx(docx_path: str, policy_path: str | None = None) -> dict[str, Any]:
    policy = load_policy(Path(policy_path) if policy_path else DEFAULT_POLICY_PATH)
    patterns = compile_patterns(policy)
    violations = []
    scanned_parts = 0

    try:
        with zipfile.ZipFile(docx_path, "r") as archive:
            for part_name in sorted(archive.namelist()):
                if not STORY_PART_RE.match(part_name):
                    continue
                text = xml_text(archive.read(part_name))
                scanned_parts += 1
                violations.extend(scan_text(text, part_name, patterns))
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        return {
            "success": False,
            "status": "error",
            "source": docx_path,
            "error": str(exc),
            "scanned_parts": scanned_parts,
            "violation_count": 0,
            "violations": [],
        }

    return {
        "success": not violations,
        "status": "pass" if not violations else "fail",
        "policy_version": policy.get("version"),
        "source": docx_path,
        "scanned_parts": scanned_parts,
        "violation_count": len(violations),
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan external-clean DOCX for internal markers.")
    parser.add_argument("docx_path")
    parser.add_argument("--policy", default=None)
    args = parser.parse_args()

    result = scan_docx(args.docx_path, args.policy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Build pending synthetic-seed review packets for external calibration.

Usage:
  python3 scripts/build_seed_review_packets.py
  python3 scripts/build_seed_review_packets.py --family nda
  python3 scripts/build_seed_review_packets.py --external-status completed
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPROVED_TEMPLATES_DIR = PROJECT_ROOT / "contract-review" / "library" / "approved" / "templates"
POLICY_PATH = PROJECT_ROOT / "contract-review" / "library" / "policies" / "seed-calibration-policy.yaml"


def load_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def make_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-")


def load_clause_rows(package_dir: Path) -> list[dict]:
    clause_rows = []
    for clause_path in sorted((package_dir / "clauses").glob("*.json")):
        clause = load_json(clause_path)
        if not isinstance(clause, dict):
            continue
        snippet = (clause.get("text") or "").strip().replace("\n", " ")
        clause_rows.append(
            {
                "clause_id": clause.get("clause_id") or clause_path.stem,
                "section_no": clause.get("section_no") or "",
                "heading": clause.get("heading") or clause.get("header") or "",
                "clause_type": clause.get("clause_type") or "unknown",
                "paragraph_count": clause.get("paragraph_count"),
                "snippet": snippet[:180] + ("..." if len(snippet) > 180 else ""),
            }
        )
    return clause_rows


def load_defined_terms(package_dir: Path) -> list[str]:
    terms = load_json(package_dir / "structure" / "defined_terms.json")
    if not isinstance(terms, list):
        return []
    return [term.get("term") for term in terms if isinstance(term, dict) and term.get("term")]


def collect_seed_packets(
    *,
    approved_templates_dir: Path,
    policy_path: Path,
    external_status_filter: str,
    family_filter: str | None,
) -> list[dict]:
    policy = load_yaml(policy_path) or {}
    synthetic_policy = policy.get("synthetic_seed", {})
    review_execution = synthetic_policy.get("review_execution", {})

    synthetic_tag = synthetic_policy.get("manifest_tag", "synthetic-seed")
    calibration_relpath = synthetic_policy.get("calibration_review_path", "quality/calibration-review.json")
    priority_order = review_execution.get("family_priority_order") or []
    family_clusters = review_execution.get("family_clusters") or {}
    cluster_checklists = review_execution.get("cluster_checklists") or {}
    priority_index = {family: idx for idx, family in enumerate(priority_order)}

    packets = []
    for manifest_path in sorted(approved_templates_dir.glob("*/*/manifest.yaml")):
        manifest = load_yaml(manifest_path)
        if not isinstance(manifest, dict):
            continue
        if synthetic_tag not in (manifest.get("tags") or []):
            continue

        package_dir = manifest_path.parent
        calibration = load_json(package_dir / calibration_relpath)
        if not isinstance(calibration, dict):
            continue

        contract_family = manifest.get("contract_family")
        if family_filter and contract_family != family_filter:
            continue

        external_status = calibration.get("external_domain_review_status")
        if external_status_filter != "all" and external_status != external_status_filter:
            continue

        cluster = family_clusters.get(contract_family, "unassigned")
        packets.append(
            {
                "priority_rank": priority_index.get(contract_family, len(priority_order) + 999),
                "contract_family": contract_family,
                "doc_id": manifest.get("doc_id"),
                "title": manifest.get("title"),
                "title_en": manifest.get("title_en"),
                "subtype": manifest.get("subtype"),
                "authority_level": manifest.get("authority_level"),
                "industry": manifest.get("industry"),
                "language": manifest.get("language"),
                "jurisdiction": manifest.get("jurisdiction"),
                "governing_law": manifest.get("governing_law"),
                "notes": manifest.get("notes"),
                "stats": manifest.get("stats") or {},
                "manifest_path": format_path(manifest_path),
                "package_dir": format_path(package_dir),
                "normalized_path": format_path(package_dir / "normalized" / "clean.md"),
                "calibration_path": format_path(package_dir / calibration_relpath),
                "external_domain_review_status": external_status,
                "promotion_recommendation": calibration.get("promotion_recommendation"),
                "promotion_blockers": calibration.get("promotion_blockers") or [],
                "review_notes": calibration.get("review_notes") or [],
                "review_cluster": cluster,
                "review_checklist": cluster_checklists.get(cluster) or [],
                "defined_terms": load_defined_terms(package_dir),
                "clauses": load_clause_rows(package_dir),
            }
        )

    packets.sort(key=lambda item: (item["priority_rank"], item["contract_family"] or "", item["doc_id"] or ""))
    return packets


def render_packet_markdown(packet: dict, generated_at: str) -> str:
    clause_lines = []
    for clause in packet["clauses"]:
        line = (
            f"- {clause['section_no']} {clause['heading']} [{clause['clause_type']}]"
            f": {clause['snippet']}"
        )
        clause_lines.append(line)

    checklist_lines = [f"- {item}" for item in packet["review_checklist"]]
    blocker_lines = [f"- {item}" for item in packet["promotion_blockers"]] or ["- (none)"]
    review_note_lines = [f"- {item}" for item in packet["review_notes"]] or ["- (none)"]
    term_preview = ", ".join(packet["defined_terms"][:12]) if packet["defined_terms"] else "(none)"

    return "\n".join(
        [
            f"# Seed Review Packet: {packet['contract_family']} / {packet['doc_id']}",
            "",
            "## Summary",
            f"- Generated at: {generated_at}",
            f"- Priority rank: {packet['priority_rank'] + 1}",
            f"- Review cluster: {packet['review_cluster']}",
            f"- Contract family: {packet['contract_family']}",
            f"- Doc ID: {packet['doc_id']}",
            f"- Title: {packet['title']} / {packet['title_en']}",
            f"- Subtype: {packet['subtype']}",
            f"- Authority level: {packet['authority_level']}",
            f"- External review status: {packet['external_domain_review_status']}",
            f"- Promotion recommendation: {packet['promotion_recommendation']}",
            f"- Industry: {packet['industry']}",
            f"- Jurisdiction: {packet['jurisdiction']}",
            f"- Governing law: {packet['governing_law']}",
            "",
            "## Package Paths",
            f"- Package dir: {packet['package_dir']}",
            f"- Manifest: {packet['manifest_path']}",
            f"- Normalized text: {packet['normalized_path']}",
            f"- Calibration metadata: {packet['calibration_path']}",
            "",
            "## Current Notes",
            f"- Manifest notes: {packet['notes']}",
            "- Promotion blockers:",
            *blocker_lines,
            "- Review notes:",
            *review_note_lines,
            "",
            "## Review Checklist",
            *checklist_lines,
            "",
            "## Structural Snapshot",
            f"- Sections: {packet['stats'].get('sections')}",
            f"- Clauses: {packet['stats'].get('total_clauses')}",
            f"- Defined terms: {packet['stats'].get('defined_terms')}",
            f"- Unmapped clauses: {packet['stats'].get('unmapped_clauses')}",
            f"- Defined term preview: {term_preview}",
            "",
            "## Clause Inventory",
            *clause_lines,
            "",
            "## Reviewer Fill-In",
            "- Reviewer name:",
            "- Reviewer role:",
            "- Reviewed at:",
            "- Decision: keep_acceptable / promote_to_preferred / needs_revision / needs_family_split",
            "- Approval note:",
            "- Follow-up edits required:",
            "",
        ]
    ).rstrip() + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_queue_markdown(packets: list[dict], generated_at: str) -> str:
    lines = [
        "# Synthetic Seed Review Queue",
        "",
        f"- Generated at: {generated_at}",
        f"- Pending packet count: {len(packets)}",
        "",
        "## Queue",
    ]
    for packet in packets:
        lines.append(
            f"- {packet['priority_rank'] + 1}. {packet['contract_family']} / {packet['doc_id']}"
            f" [{packet['review_cluster']}] status={packet['external_domain_review_status']}"
            f" recommendation={packet['promotion_recommendation']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", help="Only build packets for one contract family.")
    parser.add_argument(
        "--external-status",
        choices=["pending", "completed", "waived", "all"],
        default="pending",
        help="Filter packets by external review status.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for generated queue and packet files. Defaults to policy output dir.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    policy = load_yaml(POLICY_PATH) or {}
    output_dir = (
        PROJECT_ROOT
        / (
            args.output_dir
            or policy.get("synthetic_seed", {})
            .get("review_execution", {})
            .get("default_output_dir", "output/seed-review-packets")
        )
    )

    packets = collect_seed_packets(
        approved_templates_dir=APPROVED_TEMPLATES_DIR,
        policy_path=POLICY_PATH,
        external_status_filter=args.external_status,
        family_filter=args.family,
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    queue_payload = {
        "success": True,
        "generated_at": generated_at,
        "output_dir": str(output_dir.relative_to(PROJECT_ROOT)),
        "packet_count": len(packets),
        "packets": [],
    }

    for packet in packets:
        packet_filename = f"{packet['priority_rank'] + 1:02d}-{make_slug(packet['contract_family'])}-{make_slug(packet['doc_id'])}.md"
        packet_output = output_dir / packet_filename
        write_text(packet_output, render_packet_markdown(packet, generated_at))
        queue_payload["packets"].append(
            {
                "contract_family": packet["contract_family"],
                "doc_id": packet["doc_id"],
                "priority_rank": packet["priority_rank"] + 1,
                "review_cluster": packet["review_cluster"],
                "external_domain_review_status": packet["external_domain_review_status"],
                "promotion_recommendation": packet["promotion_recommendation"],
                "packet_path": format_path(packet_output),
                "package_dir": packet["package_dir"],
            }
        )

    write_json(output_dir / "queue.json", queue_payload)
    write_text(output_dir / "queue.md", build_queue_markdown(packets, generated_at))
    print(json.dumps(queue_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

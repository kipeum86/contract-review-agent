#!/usr/bin/env python3
"""
Summarize synthetic seed calibration status and preferred-promotion readiness.

Usage:
  python3 scripts/report_seed_calibration.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPROVED_TEMPLATES_DIR = PROJECT_ROOT / "contract-review" / "library" / "approved" / "templates"
POLICY_PATH = PROJECT_ROOT / "contract-review" / "library" / "policies" / "seed-calibration-policy.yaml"


def load_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def generate_report(
    approved_templates_dir: Path | None = None,
    policy_path: Path | None = None,
) -> dict:
    approved_templates_dir = approved_templates_dir or APPROVED_TEMPLATES_DIR
    policy_path = policy_path or POLICY_PATH

    policy = load_yaml(policy_path) or {}
    synthetic_policy = policy.get("synthetic_seed", {})
    synthetic_tag = synthetic_policy.get("manifest_tag", "synthetic-seed")
    calibration_relpath = synthetic_policy.get("calibration_review_path", "quality/calibration-review.json")
    preferred_requirements = synthetic_policy.get("preferred_authority_requires", {})
    review_execution = synthetic_policy.get("review_execution", {})
    family_priority_order = review_execution.get("family_priority_order") or []
    family_clusters = review_execution.get("family_clusters") or {}
    priority_index = {family: idx for idx, family in enumerate(family_priority_order)}

    packages = []
    missing_calibration_review = []
    preferred_gate_violations = []

    authority_counts = Counter()
    external_status_counts = Counter()
    recommendation_counts = Counter()

    required_external_status = preferred_requirements.get("external_domain_review_status")
    required_recommendation = preferred_requirements.get("promotion_recommendation")
    required_fields = preferred_requirements.get("required_external_review_fields") or []

    for manifest_path in sorted(approved_templates_dir.glob("*/*/manifest.yaml")):
        manifest = load_yaml(manifest_path)
        if not manifest:
            continue
        tags = manifest.get("tags") or []
        if synthetic_tag not in tags:
            continue

        calibration_path = manifest_path.parent / calibration_relpath
        calibration = load_json(calibration_path)
        if not calibration:
            missing_calibration_review.append(str(calibration_path.relative_to(PROJECT_ROOT)))
            continue

        authority_level = manifest.get("authority_level")
        external_status = calibration.get("external_domain_review_status")
        promotion_recommendation = calibration.get("promotion_recommendation")

        authority_counts[authority_level] += 1
        external_status_counts[external_status] += 1
        recommendation_counts[promotion_recommendation] += 1
        contract_family = manifest.get("contract_family")

        package_record = {
            "contract_family": contract_family,
            "doc_id": manifest.get("doc_id"),
            "authority_level": authority_level,
            "external_domain_review_status": external_status,
            "promotion_recommendation": promotion_recommendation,
            "promotion_blockers": calibration.get("promotion_blockers") or [],
            "review_cluster": family_clusters.get(contract_family, "unassigned"),
            "review_priority_rank": priority_index.get(contract_family, len(family_priority_order)) + 1,
        }
        packages.append(package_record)

        if authority_level == "preferred":
            external_review = calibration.get("external_review") or {}
            missing_required = [field for field in required_fields if not external_review.get(field)]
            if (
                external_status != required_external_status
                or promotion_recommendation != required_recommendation
                or missing_required
            ):
                preferred_gate_violations.append(
                    {
                        "contract_family": contract_family,
                        "doc_id": manifest.get("doc_id"),
                        "missing_required_external_review_fields": missing_required,
                        "external_domain_review_status": external_status,
                        "promotion_recommendation": promotion_recommendation,
                    }
                )

    packages.sort(key=lambda item: (item["contract_family"] or "", item["doc_id"] or ""))
    families_pending_external_review = sorted(
        {
            package["contract_family"]
            for package in packages
            if package["external_domain_review_status"] == "pending"
        }
    )
    ready_for_preferred_promotion = [
        package
        for package in packages
        if package["external_domain_review_status"] == required_external_status
        and package["promotion_recommendation"] == required_recommendation
        and not package["promotion_blockers"]
    ]
    pending_review_queue = sorted(
        [
            package
            for package in packages
            if package["external_domain_review_status"] == "pending"
        ],
        key=lambda item: (
            item.get("review_priority_rank", len(family_priority_order) + 1),
            item.get("contract_family") or "",
            item.get("doc_id") or "",
        ),
    )

    return {
        "success": True,
        "synthetic_seed_count": len(packages),
        "authority_level_counts": dict(sorted(authority_counts.items())),
        "external_domain_review_status_counts": dict(sorted(external_status_counts.items())),
        "promotion_recommendation_counts": dict(sorted(recommendation_counts.items())),
        "packages_missing_calibration_review": missing_calibration_review,
        "preferred_gate_violations": preferred_gate_violations,
        "families_pending_external_review": families_pending_external_review,
        "ready_for_preferred_promotion": ready_for_preferred_promotion,
        "pending_review_queue": pending_review_queue,
        "packages": packages,
    }


def main() -> None:
    print(json.dumps(generate_report(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

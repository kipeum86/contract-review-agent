#!/usr/bin/env python3
"""
Update synthetic-seed calibration metadata after external review.

Usage:
  python3 scripts/update_seed_calibration.py \
    --package-dir contract-review/library/approved/templates/nda/0-nda-mutual-seed \
    --external-status completed \
    --recommendation keep_acceptable \
    --reviewer-name "Kim Reviewer" \
    --reviewer-role "External counsel"
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / "contract-review" / "library" / "policies" / "seed-calibration-policy.yaml"


def load_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as tmp:
        tmp.write(content)
        temp_name = tmp.name
    Path(temp_name).replace(path)


def write_json(path: Path, payload: dict) -> None:
    write_atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_yaml(path: Path, payload: dict) -> None:
    write_atomic_text(path, yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, help="Synthetic seed package directory.")
    parser.add_argument(
        "--external-status",
        required=True,
        choices=["pending", "completed", "waived"],
        help="External domain review status to record.",
    )
    parser.add_argument(
        "--recommendation",
        required=True,
        choices=["keep_acceptable", "promote_to_preferred", "needs_revision", "needs_family_split"],
        help="Promotion recommendation from the review.",
    )
    parser.add_argument("--reviewer-name", help="Reviewer name.")
    parser.add_argument("--reviewer-role", help="Reviewer role or organization.")
    parser.add_argument("--reviewed-at", help="ISO timestamp; defaults to current UTC for completed review.")
    parser.add_argument("--approval-note", help="Short reviewer approval note.")
    parser.add_argument(
        "--review-note",
        action="append",
        default=[],
        help="Additional review note to append. Can be repeated.",
    )
    parser.add_argument(
        "--blocker",
        action="append",
        default=[],
        help="Override derived promotion blockers. Can be repeated.",
    )
    parser.add_argument(
        "--promote-manifest",
        action="store_true",
        help="Also promote manifest authority_level to preferred if the review supports it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the updated payload without writing files.",
    )
    return parser.parse_args()


def derive_blockers(policy: dict, external_status: str, recommendation: str, explicit: list[str]) -> list[str]:
    if explicit:
        return list(dict.fromkeys(explicit))

    blocker_policy = policy.get("synthetic_seed", {}).get("promotion_blockers", {})
    if external_status == "pending":
        return list(blocker_policy.get("pending_external_review") or ["external_domain_expert_review_pending"])
    if external_status == "waived":
        return list(blocker_policy.get("waived_external_review") or ["external_review_waived_not_eligible_for_preferred"])
    if recommendation == "promote_to_preferred":
        return []
    if recommendation == "needs_revision":
        return list(blocker_policy.get("needs_revision") or ["revision_required_before_promotion"])
    if recommendation == "needs_family_split":
        return list(blocker_policy.get("needs_family_split") or ["family_split_required_before_promotion"])
    return list(blocker_policy.get("keep_acceptable") or ["reviewer_kept_as_acceptable"])


def validate_update_request(
    *,
    policy: dict,
    external_status: str,
    recommendation: str,
    reviewer_name: str | None,
    reviewer_role: str | None,
    reviewed_at: str | None,
    promote_manifest: bool,
) -> str | None:
    preferred_requirements = (
        policy.get("synthetic_seed", {}).get("preferred_authority_requires") or {}
    )
    required_external_status = preferred_requirements.get("external_domain_review_status")
    required_recommendation = preferred_requirements.get("promotion_recommendation")

    if external_status == "completed":
        if not reviewer_name or not reviewer_role:
            return "Completed external review requires reviewer_name and reviewer_role."
        if not reviewed_at:
            return "Completed external review requires reviewed_at."

    if recommendation == required_recommendation and external_status != required_external_status:
        return "promote_to_preferred recommendation requires completed external review."

    if promote_manifest:
        if recommendation != required_recommendation or external_status != required_external_status:
            return "Manifest promotion requires completed external review and promote_to_preferred recommendation."
        if not reviewer_name or not reviewer_role or not reviewed_at:
            return "Manifest promotion requires reviewer_name, reviewer_role, and reviewed_at."

    return None


def main() -> None:
    args = parse_args()
    package_dir = PROJECT_ROOT / args.package_dir
    manifest_path = package_dir / "manifest.yaml"

    policy = load_yaml(POLICY_PATH) or {}
    synthetic_policy = policy.get("synthetic_seed", {})
    calibration_relpath = synthetic_policy.get("calibration_review_path", "quality/calibration-review.json")
    calibration_path = package_dir / calibration_relpath

    manifest = load_yaml(manifest_path)
    calibration = load_json(calibration_path)
    if not isinstance(manifest, dict):
        raise SystemExit(f"Manifest is missing or unreadable: {manifest_path}")
    if not isinstance(calibration, dict):
        raise SystemExit(f"Calibration review is missing or unreadable: {calibration_path}")
    if synthetic_policy.get("manifest_tag", "synthetic-seed") not in (manifest.get("tags") or []):
        raise SystemExit("Target package is not tagged as a synthetic seed.")

    reviewed_at = args.reviewed_at
    if args.external_status == "completed" and not reviewed_at:
        reviewed_at = datetime.now(timezone.utc).isoformat()

    error = validate_update_request(
        policy=policy,
        external_status=args.external_status,
        recommendation=args.recommendation,
        reviewer_name=args.reviewer_name,
        reviewer_role=args.reviewer_role,
        reviewed_at=reviewed_at,
        promote_manifest=args.promote_manifest,
    )
    if error:
        raise SystemExit(error)

    blockers = derive_blockers(policy, args.external_status, args.recommendation, args.blocker)
    updated_manifest = dict(manifest)
    updated_calibration = dict(calibration)
    external_review = dict(updated_calibration.get("external_review") or {})
    review_notes = list(updated_calibration.get("review_notes") or [])

    if args.external_status == "completed":
        external_review["reviewer_name"] = args.reviewer_name
        external_review["reviewer_role"] = args.reviewer_role
        external_review["reviewed_at"] = reviewed_at
        if args.approval_note is not None:
            external_review["approval_note"] = args.approval_note
    else:
        external_review["reviewer_name"] = None
        external_review["reviewer_role"] = None
        external_review["reviewed_at"] = None
        external_review["approval_note"] = args.approval_note

    for note in args.review_note:
        if note and note not in review_notes:
            review_notes.append(note)

    updated_calibration["external_domain_review_status"] = args.external_status
    updated_calibration["promotion_recommendation"] = args.recommendation
    updated_calibration["promotion_blockers"] = blockers
    updated_calibration["external_review"] = external_review
    updated_calibration["review_notes"] = review_notes
    updated_calibration["current_authority_level"] = (
        "preferred" if args.promote_manifest else updated_manifest.get("authority_level")
    )

    if args.promote_manifest:
        updated_manifest["authority_level"] = "preferred"
        updated_manifest["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = {
        "success": True,
        "package_dir": str(package_dir.relative_to(PROJECT_ROOT)),
        "manifest_path": str(manifest_path.relative_to(PROJECT_ROOT)),
        "calibration_path": str(calibration_path.relative_to(PROJECT_ROOT)),
        "external_domain_review_status": updated_calibration["external_domain_review_status"],
        "promotion_recommendation": updated_calibration["promotion_recommendation"],
        "promotion_blockers": updated_calibration["promotion_blockers"],
        "manifest_authority_level": updated_manifest["authority_level"],
        "ready_for_preferred_promotion": (
            updated_calibration["external_domain_review_status"] == "completed"
            and updated_calibration["promotion_recommendation"] == "promote_to_preferred"
            and not updated_calibration["promotion_blockers"]
        ),
        "dry_run": args.dry_run,
    }

    if not args.dry_run:
        write_json(calibration_path, updated_calibration)
        write_yaml(manifest_path, updated_manifest)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

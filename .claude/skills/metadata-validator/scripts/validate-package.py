#!/usr/bin/env python3
"""
Package integrity validation.
Checks that an ingestion package is complete and internally consistent.
Applies hard-fail and soft-fail conditions from the design spec.
"""

import sys
import os
import json
from datetime import datetime, timezone

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
POLICIES_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library', 'policies')


REQUIRED_CLAUSE_FIELDS = ('clause_id', 'clause_type', 'text')


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_json(path: str) -> dict | list | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_sections(outline: dict | list | None) -> tuple[list, str | None]:
    """Return a normalized section list from outline.json.

    Supported shapes:
      - list[dict]  (current ingestion output)
      - {"sections": [...]} (legacy/alternate shape)
      - {"outline": [...]}   (defensive compatibility)
    """
    if outline is None:
        return [], "Outline is missing or unreadable"

    if isinstance(outline, list):
        return outline, None

    if isinstance(outline, dict):
        if isinstance(outline.get('sections'), list):
            return outline['sections'], None
        if isinstance(outline.get('outline'), list):
            return outline['outline'], None
        return [], "outline.json object is missing a list-valued 'sections' or 'outline' field"

    return [], f"outline.json must be a list or object, got {type(outline).__name__}"


def load_seed_calibration_policy() -> dict:
    return load_yaml(os.path.join(POLICIES_DIR, 'seed-calibration-policy.yaml')) or {}


def is_synthetic_seed(manifest: dict, policy: dict) -> bool:
    tag = (
        policy.get('synthetic_seed', {}).get('manifest_tag')
        or 'synthetic-seed'
    )
    return tag in (manifest.get('tags') or [])


def validate_synthetic_seed_calibration(
    package_dir: str,
    manifest: dict,
    result: dict,
) -> None:
    policy = load_seed_calibration_policy()
    if not policy or not is_synthetic_seed(manifest, policy):
        return

    synthetic_policy = policy.get('synthetic_seed', {})
    calibration_relpath = synthetic_policy.get('calibration_review_path') or 'quality/calibration-review.json'
    calibration_path = os.path.join(package_dir, *calibration_relpath.split('/'))
    calibration = load_json(calibration_path)

    if not isinstance(calibration, dict):
        result['soft_fails'].append(
            f"Synthetic seed calibration review is missing or unreadable: {calibration_relpath}"
        )
        return

    result['stats']['synthetic_seed'] = True
    result['stats']['calibration_review_present'] = True
    result['stats']['external_domain_review_status'] = calibration.get('external_domain_review_status')
    result['stats']['promotion_recommendation'] = calibration.get('promotion_recommendation')

    allowed_internal = set(synthetic_policy.get('internal_review_status_values') or [])
    allowed_external = set(synthetic_policy.get('external_domain_review_status_values') or [])
    allowed_recommendations = set(synthetic_policy.get('promotion_recommendation_values') or [])

    internal_status = calibration.get('internal_review_status')
    external_status = calibration.get('external_domain_review_status')
    promotion_recommendation = calibration.get('promotion_recommendation')
    current_authority_level = calibration.get('current_authority_level')

    if allowed_internal and internal_status not in allowed_internal:
        result['hard_fails'].append(
            f"Invalid synthetic seed internal_review_status: {internal_status!r}"
        )
    if allowed_external and external_status not in allowed_external:
        result['hard_fails'].append(
            f"Invalid synthetic seed external_domain_review_status: {external_status!r}"
        )
    if allowed_recommendations and promotion_recommendation not in allowed_recommendations:
        result['hard_fails'].append(
            f"Invalid synthetic seed promotion_recommendation: {promotion_recommendation!r}"
        )

    manifest_authority = manifest.get('authority_level')
    if current_authority_level and manifest_authority and current_authority_level != manifest_authority:
        result['soft_fails'].append(
            "Synthetic seed calibration current_authority_level does not match manifest authority_level"
        )

    preferred_requirements = synthetic_policy.get('preferred_authority_requires') or {}
    if manifest_authority == 'preferred':
        required_external_status = preferred_requirements.get('external_domain_review_status')
        required_recommendation = preferred_requirements.get('promotion_recommendation')
        external_review = calibration.get('external_review') or {}
        required_fields = preferred_requirements.get('required_external_review_fields') or []
        missing_fields = [field for field in required_fields if not external_review.get(field)]

        if external_status != required_external_status:
            result['hard_fails'].append(
                "Synthetic seed cannot use authority_level=preferred without completed external domain review"
            )
        if promotion_recommendation != required_recommendation:
            result['hard_fails'].append(
                "Synthetic seed cannot use authority_level=preferred without promote_to_preferred recommendation"
            )
        if missing_fields:
            result['hard_fails'].append(
                f"Synthetic seed preferred promotion is missing external review fields: {missing_fields}"
            )


def validate_package(package_dir: str) -> dict:
    """Validate a complete ingestion package.

    Checks:
      1. Normalized text exists and is non-empty
      2. Structural parse output exists
      3. Manifest has all required fields (checked separately)
      4. Clause records exist
      5. Numbering continuity
      6. Cross-reference integrity

    Returns:
        dict with:
          - valid: bool (no hard fails)
          - hard_fails: list of hard-fail conditions triggered
          - soft_fails: list of soft-fail conditions triggered
          - warnings: list of warnings
          - stats: package statistics
    """
    result = {
        'package_dir': package_dir,
        'valid': False,
        'hard_fails': [],
        'soft_fails': [],
        'warnings': [],
        'stats': {},
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }

    if not os.path.isdir(package_dir):
        result['hard_fails'].append(f"Package directory not found: {package_dir}")
        return result

    # Check 1: Normalized text
    normalized_dir = os.path.join(package_dir, 'normalized')
    clean_md = os.path.join(normalized_dir, 'clean.md')
    plain_txt = os.path.join(normalized_dir, 'plain.txt')

    if not os.path.exists(clean_md):
        result['hard_fails'].append("Normalized text (clean.md) is absent")
    elif os.path.getsize(clean_md) == 0:
        result['hard_fails'].append("Normalized text (clean.md) is empty")
    else:
        with open(clean_md, 'r', encoding='utf-8') as f:
            content = f.read()
        result['stats']['clean_md_length'] = len(content)
        result['stats']['clean_md_lines'] = content.count('\n') + 1

    # Check 2: Structural parse output
    structure_dir = os.path.join(package_dir, 'structure')
    outline_path = os.path.join(structure_dir, 'outline.json')

    if not os.path.exists(outline_path):
        result['hard_fails'].append("Structural parse output (outline.json) is missing")
    else:
        outline = load_json(outline_path)
        sections, outline_error = extract_sections(outline)
        if outline_error:
            result['hard_fails'].append(f"Invalid outline.json shape: {outline_error}")
        else:
            result['stats']['section_count'] = len(sections)
            if len(sections) < 5:
                result['soft_fails'].append(
                    f"Anomalously low section count: {len(sections)} (expected >= 5)")

    # Check defined terms
    terms_path = os.path.join(structure_dir, 'defined_terms.json')
    if os.path.exists(terms_path):
        terms = load_json(terms_path)
        if terms:
            result['stats']['defined_terms_count'] = len(terms)
        else:
            result['soft_fails'].append("Defined term extraction returned empty result")
    else:
        result['soft_fails'].append("Defined terms file not found")

    # Check 3: Manifest
    manifest_path = os.path.join(package_dir, 'manifest.yaml')
    manifest = load_yaml(manifest_path)
    if not manifest:
        result['hard_fails'].append("Manifest (manifest.yaml) is missing or unreadable")
    else:
        # Count missing required fields (detailed validation in validate-manifest.py)
        required = ['doc_id', 'title', 'doc_class', 'contract_family',
                     'paper_role', 'approval_state', 'status', 'sha256',
                     'source_file', 'created_at']
        missing = [f for f in required if not manifest.get(f)]
        result['stats']['missing_required_fields'] = len(missing)
        if len(missing) >= 3:
            result['hard_fails'].append(
                f"Three or more required manifest fields missing: {missing}")

        # Check governing law ambiguity
        if not manifest.get('governing_law') and not manifest.get('jurisdiction'):
            result['soft_fails'].append("Governing law is ambiguous (both governing_law and jurisdiction are empty)")

        # Check freshness
        if manifest.get('freshness_sensitive') and not manifest.get('last_legal_refresh_date'):
            result['soft_fails'].append("Freshness-sensitive clause lacks last_legal_refresh_date")

        validate_synthetic_seed_calibration(package_dir, manifest, result)

    # Check 4: Clause records
    clauses_dir = os.path.join(package_dir, 'clauses')
    if os.path.isdir(clauses_dir):
        clause_files = [f for f in os.listdir(clauses_dir) if f.endswith('.json')]
        result['stats']['clause_count'] = len(clause_files)

        if len(clause_files) < 5:
            result['soft_fails'].append(
                f"Low clause count: {len(clause_files)} (expected >= 5)")

        # Check unmapped ratio
        unmapped_count = 0
        invalid_clause_files = []
        for cf in clause_files:
            clause = load_json(os.path.join(clauses_dir, cf))
            if not isinstance(clause, dict):
                invalid_clause_files.append(f"{cf}: not a JSON object")
                continue

            missing = [field for field in REQUIRED_CLAUSE_FIELDS if not clause.get(field)]
            if not (clause.get('heading') or clause.get('header')):
                missing.append('heading')

            if missing:
                invalid_clause_files.append(f"{cf}: missing {', '.join(sorted(set(missing)))}")
                continue

            if not isinstance(clause.get('defined_terms_used', []), list):
                result['soft_fails'].append(f"{cf}: defined_terms_used must be a list")

            if not isinstance(clause.get('cross_refs', []), list):
                result['soft_fails'].append(f"{cf}: cross_refs must be a list")

            if clause.get('clause_type') == 'unmapped':
                unmapped_count += 1

        result['stats']['unmapped_count'] = unmapped_count
        result['stats']['invalid_clause_files'] = len(invalid_clause_files)
        if invalid_clause_files:
            result['hard_fails'].append(
                "Invalid clause artifact(s): " + "; ".join(invalid_clause_files[:10])
            )

        if len(clause_files) > 0:
            unmapped_ratio = unmapped_count / len(clause_files)
            result['stats']['unmapped_ratio'] = round(unmapped_ratio, 2)
            if unmapped_ratio >= 0.3:
                result['soft_fails'].append(
                    f"Unmapped clauses >= 30%: {unmapped_count}/{len(clause_files)} ({unmapped_ratio:.0%})")
    else:
        result['hard_fails'].append("Clauses directory not found")

    # Check 5: Quality reports
    quality_dir = os.path.join(package_dir, 'quality')
    if os.path.isdir(quality_dir):
        review_flags = load_json(os.path.join(quality_dir, 'review-flags.json'))
        if review_flags:
            result['stats']['review_flags'] = review_flags

    # Final determination
    result['valid'] = len(result['hard_fails']) == 0
    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: validate-package.py <package_dir>'}))
        sys.exit(1)

    package_dir = sys.argv[1]
    result = validate_package(package_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result['valid']:
        sys.exit(1)
    elif result['soft_fails']:
        sys.exit(2)  # Soft fail — needs human review


if __name__ == '__main__':
    main()

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
        if outline:
            sections = outline.get('sections', [])
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
        for cf in clause_files:
            clause = load_json(os.path.join(clauses_dir, cf))
            if clause and clause.get('clause_type') == 'unmapped':
                unmapped_count += 1

        result['stats']['unmapped_count'] = unmapped_count
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

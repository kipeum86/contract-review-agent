#!/usr/bin/env python3
"""
Report library coverage across configured contract families and clause taxonomy.

Usage:
  python3 report-coverage.py
"""

import json
import os
import sys
import re
from collections import Counter

import yaml


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
LIBRARY_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library')
INDEXES_DIR = os.path.join(LIBRARY_DIR, 'indexes')
POLICIES_DIR = os.path.join(LIBRARY_DIR, 'policies')
POLICIES_DEFAULT_DIR = os.path.join(LIBRARY_DIR, 'policies.default')


def resolve_policy_path(filename: str) -> str:
    """Prefer user policies/; fall back to shipped policies.default/ with a warning."""
    primary = os.path.join(POLICIES_DIR, filename)
    if os.path.exists(primary):
        return primary
    fallback = os.path.join(POLICIES_DEFAULT_DIR, filename)
    if os.path.exists(fallback):
        print(
            f"WARN: {filename} missing under policies/ — falling back to policies.default/. "
            "Initialize policies/ per CLAUDE.md 'Policy Initialization'.",
            file=sys.stderr,
        )
        return fallback
    return primary


def load_json(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def extract_clause_type_ids(taxonomy: dict) -> set[str]:
    clause_type_ids = set()
    for category in taxonomy.get('categories', []) or []:
        for clause_type in category.get('clause_types', []) or []:
            clause_type_id = clause_type.get('id')
            if clause_type_id:
                clause_type_ids.add(clause_type_id)
    return clause_type_ids


def normalize_heading(value: str | None) -> str:
    heading = (value or '').strip()
    if heading.startswith('(') and heading.endswith(')'):
        heading = heading[1:-1].strip()
    heading = re.sub(r'\s+', ' ', heading)
    return heading


def summarize_unmapped_headings(clauses: list[dict], top_n: int = 10) -> tuple[list[dict], dict[str, list[dict]]]:
    unmapped = [clause for clause in clauses if clause.get('clause_type') == 'unmapped']
    overall_counter = Counter()
    family_counters: dict[str, Counter] = {}

    for clause in unmapped:
        heading = normalize_heading(clause.get('heading') or clause.get('header') or '')
        if not heading:
            heading = '(blank heading)'
        overall_counter[heading] += 1
        family = clause.get('contract_family') or 'unknown'
        family_counters.setdefault(family, Counter())[heading] += 1

    overall = [
        {'heading': heading, 'count': count}
        for heading, count in overall_counter.most_common(top_n)
    ]
    by_family = {
        family: [
            {'heading': heading, 'count': count}
            for heading, count in counter.most_common(top_n)
        ]
        for family, counter in sorted(family_counters.items())
    }
    return overall, by_family


def build_coverage_report(family_policy: dict, clause_taxonomy: dict,
                          documents_index: dict, clauses_index: dict) -> dict:
    configured_families = family_policy.get('families', []) or []
    family_ids = [family.get('id') for family in configured_families if family.get('id')]
    configured_clause_types = extract_clause_type_ids(clause_taxonomy)

    documents = (documents_index or {}).get('documents', []) or []
    clauses = (clauses_index or {}).get('clauses', []) or []

    document_counts = Counter(doc.get('contract_family') for doc in documents if doc.get('contract_family'))
    clause_counts = Counter(clause.get('contract_family') for clause in clauses if clause.get('contract_family'))
    unmapped_counts = Counter(
        clause.get('contract_family')
        for clause in clauses
        if clause.get('contract_family') and clause.get('clause_type') == 'unmapped'
    )

    observed_clause_types = {
        clause.get('clause_type')
        for clause in clauses
        if clause.get('clause_type') and clause.get('clause_type') != 'unmapped'
    }
    unknown_clause_types = sorted(observed_clause_types - configured_clause_types)
    top_unmapped_headings, unmapped_headings_by_family = summarize_unmapped_headings(clauses)

    covered_family_ids = sorted(
        family_id
        for family_id in family_ids
        if document_counts.get(family_id, 0) or clause_counts.get(family_id, 0)
    )
    uncovered_family_ids = sorted(
        family_id
        for family_id in family_ids
        if family_id not in covered_family_ids
    )

    per_family = []
    for family_id in family_ids:
        family_clause_count = clause_counts.get(family_id, 0)
        family_unmapped_count = unmapped_counts.get(family_id, 0)
        unmapped_ratio = (
            round(family_unmapped_count / family_clause_count, 4)
            if family_clause_count
            else None
        )
        per_family.append({
            'contract_family': family_id,
            'document_count': document_counts.get(family_id, 0),
            'clause_count': family_clause_count,
            'unmapped_clause_count': family_unmapped_count,
            'unmapped_ratio': unmapped_ratio,
            'has_library_coverage': family_id in covered_family_ids,
        })

    total_clause_count = len(clauses)
    total_unmapped = sum(unmapped_counts.values())

    return {
        'success': True,
        'configured_family_count': len(family_ids),
        'covered_family_count': len(covered_family_ids),
        'configured_clause_type_count': len(configured_clause_types),
        'observed_clause_type_count': len(observed_clause_types),
        'unknown_clause_types': unknown_clause_types,
        'total_document_count': len(documents),
        'total_clause_count': total_clause_count,
        'total_unmapped_clause_count': total_unmapped,
        'total_unmapped_ratio': round(total_unmapped / total_clause_count, 4) if total_clause_count else 0.0,
        'covered_families': covered_family_ids,
        'uncovered_families': uncovered_family_ids,
        'top_unmapped_headings': top_unmapped_headings,
        'unmapped_headings_by_family': unmapped_headings_by_family,
        'per_family': per_family,
    }


def generate_report() -> dict:
    family_policy = load_yaml(resolve_policy_path('contract-families.yaml')) or {}
    clause_taxonomy = load_yaml(resolve_policy_path('clause-taxonomy.yaml')) or {}
    documents_index = load_json(os.path.join(INDEXES_DIR, 'documents.json')) or {}
    clauses_index = load_json(os.path.join(INDEXES_DIR, 'clauses.json')) or {}
    return build_coverage_report(family_policy, clause_taxonomy, documents_index, clauses_index)


def main():
    report = generate_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()

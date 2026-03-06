#!/usr/bin/env python3
"""
Index query engine.
Implements the 2-stage deterministic filtering + exclusion pipeline
for library candidate retrieval (Workflow 2, Step 5).
"""

import sys
import os
import json
from datetime import datetime, timezone, timedelta

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
LIBRARY_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library')
INDEXES_DIR = os.path.join(LIBRARY_DIR, 'indexes')
POLICIES_DIR = os.path.join(LIBRARY_DIR, 'policies')


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


def stage_1_filter(clauses: list, contract_family: str,
                   jurisdiction: str = None, governing_law: str = None) -> list:
    """Stage 1 — Deterministic filter by contract_family, jurisdiction, governing_law,
    approval_state=approved, status=active."""
    filtered = []
    for c in clauses:
        # Must match contract_family
        if c.get('contract_family') != contract_family:
            continue
        # Must be approved and active
        if c.get('approval_state') != 'approved':
            continue
        if c.get('status') != 'active':
            continue
        # Jurisdiction: match if specified (null matches any)
        if jurisdiction and c.get('jurisdiction'):
            if c['jurisdiction'] != jurisdiction:
                continue
        # Governing law: match if specified
        if governing_law and c.get('governing_law'):
            if c['governing_law'] != governing_law:
                continue
        filtered.append(c)
    return filtered


def stage_1_5_filter(candidates: list, target_clause_type: str) -> list:
    """Stage 1.5 — Narrowing filter by clause_type.
    Applied when Stage 1 returns > 50 candidates."""
    return [c for c in candidates if c.get('clause_type') == target_clause_type]


def stage_2_exclude(candidates: list, external_context: bool = False) -> list:
    """Stage 2 — Exclusion rules: remove archived, superseded (with successor), quarantined.
    If external_context=True, also exclude external_unsafe records."""
    filtered = []
    for c in candidates:
        if c.get('status') == 'archived':
            continue
        if c.get('approval_state') == 'quarantined':
            continue
        if c.get('status') == 'superseded':
            continue
        if external_context and not c.get('external_safe', False):
            continue
        filtered.append(c)
    return filtered


def apply_freshness_rules(candidates: list, config: dict) -> list:
    """Down-rank or exclude stale freshness-sensitive records."""
    stale_days = config.get('stale_threshold_days', 365)
    handling = config.get('stale_handling', 'downrank')
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

    fresh = []
    stale = []
    for c in candidates:
        if not c.get('freshness_sensitive', False):
            fresh.append(c)
            continue
        refresh_date = c.get('last_legal_refresh_date')
        if refresh_date:
            try:
                rd = datetime.fromisoformat(refresh_date)
                if rd.tzinfo is None:
                    rd = rd.replace(tzinfo=timezone.utc)
                if rd < cutoff:
                    if handling == 'exclude':
                        continue
                    stale.append(c)
                    continue
            except (ValueError, TypeError):
                pass
        fresh.append(c)

    if handling == 'downrank':
        return fresh + stale
    return fresh


def query(contract_family: str, target_clauses: list = None,
          jurisdiction: str = None, governing_law: str = None,
          external_context: bool = False) -> dict:
    """Run the full retrieval pipeline.

    Args:
        contract_family: target contract family ID
        target_clauses: list of dicts with clause_type for per-clause matching
        jurisdiction: optional jurisdiction filter
        governing_law: optional governing law filter
        external_context: if True, exclude external_unsafe records

    Returns:
        dict with candidates per clause type and overall stats
    """
    clauses_index = load_json(os.path.join(INDEXES_DIR, 'clauses.json'))
    if not clauses_index or not clauses_index.get('clauses'):
        return {
            'success': True,
            'library_empty': True,
            'message': 'Library is empty. Proceeding in general review mode.',
            'candidates': {},
            'total_candidates': 0,
        }

    all_clauses = clauses_index['clauses']

    # Stage 1
    stage1_result = stage_1_filter(all_clauses, contract_family, jurisdiction, governing_law)

    # Stage 2 exclusion
    stage2_result = stage_2_exclude(stage1_result, external_context)

    # Load freshness rules
    retrieval_config = load_yaml(os.path.join(POLICIES_DIR, 'retrieval-priority.yaml'))
    freshness_rules = {}
    if retrieval_config:
        freshness_rules = retrieval_config.get('freshness_rules', {})
    stage2_result = apply_freshness_rules(stage2_result, freshness_rules)

    # If target clauses provided, apply Stage 1.5 per clause
    candidates = {}
    if target_clauses:
        threshold = 50
        if retrieval_config:
            stage_1_5 = retrieval_config.get('filter_rules', {}).get('stage_1_5', {})
            threshold = stage_1_5.get('trigger_threshold', 50)

        for tc in target_clauses:
            ct = tc.get('clause_type', 'unmapped')
            if len(stage2_result) > threshold:
                per_clause = stage_1_5_filter(stage2_result, ct)
            else:
                per_clause = [c for c in stage2_result if c.get('clause_type') == ct]
            # If no exact match, include all stage2 results for LLM matching
            if not per_clause:
                per_clause = stage2_result
            candidates[ct] = per_clause
    else:
        candidates['_all'] = stage2_result

    total = sum(len(v) for v in candidates.values())
    return {
        'success': True,
        'library_empty': False,
        'contract_family': contract_family,
        'stage_1_count': len(stage1_result),
        'stage_2_count': len(stage2_result),
        'total_candidates': total,
        'candidates': candidates,
    }


def search(query_text: str = None, clause_type: str = None,
           contract_family: str = None, doc_class: str = None) -> dict:
    """General-purpose search across clause and document indexes.

    Returns matching results for display to the user.
    """
    results = {'documents': [], 'clauses': []}

    # Search documents
    docs_index = load_json(os.path.join(INDEXES_DIR, 'documents.json'))
    if docs_index:
        for doc in docs_index.get('documents', []):
            match = True
            if contract_family and doc.get('contract_family') != contract_family:
                match = False
            if doc_class and doc.get('doc_class') != doc_class:
                match = False
            if query_text:
                searchable = ' '.join(str(v) for v in doc.values() if v).lower()
                if query_text.lower() not in searchable:
                    match = False
            if match:
                results['documents'].append(doc)

    # Search clauses
    clauses_index = load_json(os.path.join(INDEXES_DIR, 'clauses.json'))
    if clauses_index:
        for clause in clauses_index.get('clauses', []):
            match = True
            if clause_type and clause.get('clause_type') != clause_type:
                match = False
            if contract_family and clause.get('contract_family') != contract_family:
                match = False
            if query_text:
                searchable = ' '.join(str(v) for v in clause.values() if v).lower()
                if query_text.lower() not in searchable:
                    match = False
            if match:
                results['clauses'].append(clause)

    return {
        'success': True,
        'documents_found': len(results['documents']),
        'clauses_found': len(results['clauses']),
        'results': results,
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'error': 'Usage: query-index.py <query|search> [options as JSON]'
        }))
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'query':
        # Read query parameters from stdin or args
        if len(sys.argv) > 2:
            params = json.loads(sys.argv[2])
        else:
            params = json.loads(sys.stdin.read())
        result = query(**params)
    elif mode == 'search':
        if len(sys.argv) > 2:
            params = json.loads(sys.argv[2])
        else:
            params = json.loads(sys.stdin.read())
        result = search(**params)
    else:
        result = {'error': f'Unknown mode: {mode}'}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

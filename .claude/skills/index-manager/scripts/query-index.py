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


def load_clause_texts() -> dict:
    """Load clause-texts.json for text hydration of final candidates."""
    texts_index = load_json(os.path.join(INDEXES_DIR, 'clause-texts.json'))
    if texts_index and isinstance(texts_index.get('texts'), dict):
        return texts_index['texts']
    return {}


def hydrate_candidates_text(candidates: dict, texts: dict) -> None:
    """Add 'text' field to each candidate from the clause-texts lookup."""
    for clause_list in candidates.values():
        for clause in clause_list:
            key = f"{clause.get('doc_id')}::{clause.get('clause_id')}"
            if 'text' not in clause and key in texts:
                clause['text'] = texts[key]


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def stage_1_filter(clauses: list, contract_families: list[str] | set[str],
                   jurisdiction: str = None, governing_law: str = None) -> list:
    """Stage 1 — Deterministic filter by family, jurisdiction, governing_law,
    approval_state=approved, status=active."""
    if isinstance(contract_families, str):
        contract_families = {contract_families}
    else:
        contract_families = set(contract_families or [])

    filtered = []
    for c in clauses:
        if c.get('contract_family') not in contract_families:
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


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_stale(candidate: dict, config: dict) -> bool:
    if not candidate.get('freshness_sensitive', False):
        return False

    stale_days = config.get('stale_threshold_days', 365)
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    refresh_date = parse_iso_datetime(candidate.get('last_legal_refresh_date'))
    if refresh_date is None:
        return False
    return refresh_date < cutoff


def apply_freshness_rules(candidates: list, config: dict) -> list:
    """Down-rank or exclude stale freshness-sensitive records."""
    handling = config.get('stale_handling', 'downrank')

    fresh = []
    stale = []
    for c in candidates:
        if not is_stale(c, config):
            fresh.append(c)
            continue
        if handling == 'exclude':
            continue
        stale.append(c)

    if handling == 'downrank':
        return fresh + stale
    return fresh


def load_priority_ranks(retrieval_config: dict) -> tuple[dict[str, int], int]:
    priority_order = retrieval_config.get('priority_order', {}) or {}
    rank_map = {}

    for raw_rank, bucket_name in priority_order.items():
        try:
            rank = int(raw_rank)
        except (TypeError, ValueError):
            continue
        if isinstance(bucket_name, str):
            rank_map[bucket_name] = rank

    default_rank = max(rank_map.values(), default=0) + 1
    return rank_map, default_rank


def classify_priority_bucket(candidate: dict) -> str:
    authority_level = (candidate.get('authority_level') or '').lower()
    doc_class = (candidate.get('doc_class') or '').lower()
    approval_state = (candidate.get('approval_state') or '').lower()
    status = (candidate.get('status') or '').lower()

    if doc_class == 'template':
        if authority_level == 'preferred':
            return 'preferred_template'
        if authority_level == 'acceptable':
            return 'acceptable_template'
        if authority_level == 'fallback':
            return 'fallback_template'

    if (
        candidate.get('reference_only') is True
        or approval_state == 'reference_only'
        or status == 'reference_only'
    ):
        return 'reference_only'

    return 'approved_precedent'


def language_preference_rank(candidate: dict, requested_language: str | None) -> int:
    if not requested_language:
        return 0

    candidate_language = (candidate.get('language') or '').strip().lower()
    requested_language = requested_language.strip().lower()

    if candidate_language == requested_language:
        return 0
    if not candidate_language:
        return 1
    return 2


def enrich_candidates(candidates: list, requested_language: str | None,
                      priority_ranks: dict[str, int], default_priority_rank: int,
                      family_match_type: str, family_penalty: int,
                      freshness_rules: dict) -> list:
    enriched = []
    for candidate in candidates:
        record = dict(candidate)
        priority_bucket = classify_priority_bucket(record)
        record['priority_bucket'] = priority_bucket
        record['priority_rank'] = priority_ranks.get(priority_bucket, default_priority_rank)
        record['family_match_type'] = family_match_type
        record['family_match_penalty'] = family_penalty
        record['source_contract_family'] = record.get('contract_family')
        record['language_requested'] = requested_language
        record['language_preference_rank'] = language_preference_rank(record, requested_language)
        record['freshness_rank'] = 1 if is_stale(record, freshness_rules) else 0
        enriched.append(record)
    return enriched


def sort_candidates(candidates: list) -> list:
    return sorted(
        candidates,
        key=lambda c: (
            c.get('freshness_rank', 0),
            c.get('family_match_penalty', 0),
            c.get('priority_rank', 999),
            c.get('language_preference_rank', 0),
            c.get('source_contract_family') or '',
            c.get('doc_id') or '',
            c.get('clause_id') or '',
        ),
    )


def resolve_affinity_candidates(all_clauses: list, contract_family: str,
                                jurisdiction: str, governing_law: str,
                                external_context: bool, retrieval_config: dict,
                                freshness_rules: dict,
                                requested_language: str | None,
                                priority_ranks: dict[str, int],
                                default_priority_rank: int) -> tuple[list, list[str]]:
    affinity_config = retrieval_config.get('filter_rules', {}).get('stage_3_affinity', {}) or {}
    affinity_groups = affinity_config.get('affinity_groups', []) or []
    minimum_exact_candidates = affinity_config.get('minimum_exact_candidates', 3)
    penalty = affinity_config.get('penalty', 1)

    related_families = []
    for group in affinity_groups:
        if contract_family in group:
            related_families = [family for family in group if family != contract_family]
            break

    if not related_families or minimum_exact_candidates <= 0:
        return [], []

    stage1_result = stage_1_filter(all_clauses, related_families, jurisdiction, governing_law)
    stage2_result = stage_2_exclude(stage1_result, external_context)
    stage2_result = apply_freshness_rules(stage2_result, freshness_rules)
    if not stage2_result:
        return [], related_families

    enriched = enrich_candidates(
        stage2_result,
        requested_language=requested_language,
        priority_ranks=priority_ranks,
        default_priority_rank=default_priority_rank,
        family_match_type='affinity',
        family_penalty=penalty,
        freshness_rules=freshness_rules,
    )
    return sort_candidates(enriched), related_families


def query(contract_family: str, target_clauses: list = None,
          jurisdiction: str = None, governing_law: str = None,
          external_context: bool = False, language: str = None) -> dict:
    """Run the full retrieval pipeline.

    Args:
        contract_family: target contract family ID
        target_clauses: list of dicts with clause_type for per-clause matching
        jurisdiction: optional jurisdiction filter
        governing_law: optional governing law filter
        external_context: if True, exclude external_unsafe records
        language: optional requested language for soft ranking preference

    Returns:
        dict with candidates per clause type and overall stats
    """
    clauses_index = load_json(os.path.join(INDEXES_DIR, 'clauses.json'))
    if not clauses_index or not clauses_index.get('clauses'):
        return {
            'success': True,
            'library_empty': True,
            'general_review_mode': True,
            'fallback_reason': 'library_empty',
            'message': 'Library is empty. Proceeding in general review mode.',
            'candidates': {},
            'total_candidates': 0,
        }

    all_clauses = clauses_index['clauses']
    active_approved_clauses = [
        c for c in all_clauses
        if c.get('approval_state') == 'approved' and c.get('status') == 'active'
    ]

    if not active_approved_clauses:
        return {
            'success': True,
            'library_empty': True,
            'general_review_mode': True,
            'fallback_reason': 'no_active_approved_library_records',
            'message': (
                'No active approved library records are available for retrieval. '
                'Proceeding in general review mode.'
            ),
            'candidates': {},
            'total_candidates': 0,
            'active_approved_count': 0,
        }

    # Load freshness rules
    retrieval_config = load_yaml(os.path.join(POLICIES_DIR, 'retrieval-priority.yaml')) or {}
    freshness_rules = retrieval_config.get('freshness_rules', {}) or {}
    priority_ranks, default_priority_rank = load_priority_ranks(retrieval_config)

    # Stage 1
    stage1_result = stage_1_filter(active_approved_clauses, contract_family, jurisdiction, governing_law)

    # Stage 2 exclusion
    stage2_result = stage_2_exclude(stage1_result, external_context)
    stage2_result = apply_freshness_rules(stage2_result, freshness_rules)

    combined_candidates = enrich_candidates(
        stage2_result,
        requested_language=language,
        priority_ranks=priority_ranks,
        default_priority_rank=default_priority_rank,
        family_match_type='exact',
        family_penalty=0,
        freshness_rules=freshness_rules,
    )

    affinity_config = retrieval_config.get('filter_rules', {}).get('stage_3_affinity', {}) or {}
    minimum_exact_candidates = affinity_config.get('minimum_exact_candidates', 3)
    affinity_candidates = []
    affinity_families = []
    affinity_expanded = False

    if len(stage2_result) < minimum_exact_candidates:
        affinity_candidates, affinity_families = resolve_affinity_candidates(
            active_approved_clauses,
            contract_family=contract_family,
            jurisdiction=jurisdiction,
            governing_law=governing_law,
            external_context=external_context,
            retrieval_config=retrieval_config,
            freshness_rules=freshness_rules,
            requested_language=language,
            priority_ranks=priority_ranks,
            default_priority_rank=default_priority_rank,
        )
        if affinity_candidates:
            affinity_expanded = True
            combined_candidates.extend(affinity_candidates)

    combined_candidates = sort_candidates(combined_candidates)

    # If target clauses provided, apply Stage 1.5 per clause
    candidates = {}
    if target_clauses:
        threshold = 50
        stage_1_5 = retrieval_config.get('filter_rules', {}).get('stage_1_5', {})
        threshold = stage_1_5.get('trigger_threshold', 50)

        for tc in target_clauses:
            ct = tc.get('clause_type', 'unmapped')
            if len(combined_candidates) > threshold:
                per_clause = stage_1_5_filter(combined_candidates, ct)
            else:
                per_clause = [c for c in combined_candidates if c.get('clause_type') == ct]
            # If no exact match, include the full ranked candidate set for LLM matching
            if not per_clause:
                per_clause = combined_candidates
            candidates[ct] = per_clause
    else:
        candidates['_all'] = combined_candidates

    total = sum(len(v) for v in candidates.values())
    general_review_mode = total == 0
    fallback_reason = None
    message = None

    if general_review_mode:
        fallback_reason = 'no_usable_candidates'
        message = (
            'No usable library candidates matched the requested family/filters. '
            'Proceeding in general review mode without house position comparison.'
        )

    # Hydrate text for final candidates from separate clause-texts index
    if total > 0:
        texts = load_clause_texts()
        if texts:
            hydrate_candidates_text(candidates, texts)

    return {
        'success': True,
        'library_empty': False,
        'general_review_mode': general_review_mode,
        'fallback_reason': fallback_reason,
        'message': message,
        'contract_family': contract_family,
        'language': language,
        'active_approved_count': len(active_approved_clauses),
        'stage_1_count': len(stage1_result),
        'stage_2_count': len(stage2_result),
        'affinity_expanded': affinity_expanded,
        'affinity_families': affinity_families,
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
    clause_texts = load_clause_texts() if query_text else {}
    if clauses_index:
        for clause in clauses_index.get('clauses', []):
            match = True
            if clause_type and clause.get('clause_type') != clause_type:
                match = False
            if contract_family and clause.get('contract_family') != contract_family:
                match = False
            if query_text:
                text_key = f"{clause.get('doc_id')}::{clause.get('clause_id')}"
                clause_text = clause_texts.get(text_key, '')
                searchable = ' '.join(str(v) for v in clause.values() if v).lower()
                searchable += ' ' + clause_text.lower()
                if query_text.lower() not in searchable:
                    match = False
            if match:
                text_key = f"{clause.get('doc_id')}::{clause.get('clause_id')}"
                if text_key in clause_texts:
                    clause = dict(clause)
                    clause['text'] = clause_texts[text_key]
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

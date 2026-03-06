#!/usr/bin/env python3
"""
Clause-level diff between negotiation rounds.
Compares clause records from two rounds and classifies each as:
  unchanged, modified, added, or removed.
"""

import sys
import os
import json
from difflib import SequenceMatcher


def load_clauses(clauses_dir: str) -> list[dict]:
    """Load all clause JSON files from a directory."""
    if not os.path.isdir(clauses_dir):
        return []

    clauses = []
    for fn in sorted(os.listdir(clauses_dir)):
        if fn.endswith('.json'):
            with open(os.path.join(clauses_dir, fn), 'r', encoding='utf-8') as f:
                clause = json.load(f)
                clause['_source_file'] = fn
                clauses.append(clause)
    return clauses


def text_similarity(text1: str, text2: str) -> float:
    """Compute similarity ratio between two texts."""
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()


def match_clauses(current: list[dict], prior: list[dict]) -> list[dict]:
    """Match clauses between two rounds by clause_type and position.

    Returns a list of diff entries.
    """
    diffs = []

    # Index prior clauses by clause_type for matching
    prior_by_type: dict[str, list[dict]] = {}
    for pc in prior:
        ct = pc.get('clause_type', 'unmapped')
        if ct not in prior_by_type:
            prior_by_type[ct] = []
        prior_by_type[ct].append(pc)

    matched_prior_ids = set()

    for cc in current:
        ct = cc.get('clause_type', 'unmapped')
        cc_text = cc.get('text', '')
        cc_id = cc.get('clause_id', cc.get('_source_file', ''))

        best_match = None
        best_similarity = 0.0

        # Try to match with prior clauses of the same type
        candidates = prior_by_type.get(ct, [])
        for pc in candidates:
            pc_id = pc.get('clause_id', pc.get('_source_file', ''))
            if pc_id in matched_prior_ids:
                continue
            sim = text_similarity(cc_text, pc.get('text', ''))
            if sim > best_similarity:
                best_similarity = sim
                best_match = pc

        if best_match and best_similarity > 0.3:
            best_match_id = best_match.get('clause_id', best_match.get('_source_file', ''))
            matched_prior_ids.add(best_match_id)

            if best_similarity > 0.95:
                diff_status = 'unchanged'
            else:
                diff_status = 'modified'

            diffs.append({
                'clause_id': cc_id,
                'clause_type': ct,
                'section_no': cc.get('section_no'),
                'heading': cc.get('heading'),
                'diff_status': diff_status,
                'similarity': round(best_similarity, 3),
                'prior_clause_id': best_match_id,
                'current_text_preview': cc_text[:200] if cc_text else '',
                'prior_text_preview': best_match.get('text', '')[:200],
            })
        else:
            # No match found — this is a new clause
            diffs.append({
                'clause_id': cc_id,
                'clause_type': ct,
                'section_no': cc.get('section_no'),
                'heading': cc.get('heading'),
                'diff_status': 'added',
                'similarity': 0.0,
                'prior_clause_id': None,
                'current_text_preview': cc_text[:200] if cc_text else '',
            })

    # Find removed clauses (in prior but not matched)
    for pc in prior:
        pc_id = pc.get('clause_id', pc.get('_source_file', ''))
        if pc_id not in matched_prior_ids:
            diffs.append({
                'clause_id': pc_id,
                'clause_type': pc.get('clause_type', 'unmapped'),
                'section_no': pc.get('section_no'),
                'heading': pc.get('heading'),
                'diff_status': 'removed',
                'similarity': 0.0,
                'prior_clause_id': pc_id,
                'prior_text_preview': pc.get('text', '')[:200],
            })

    return diffs


def diff_rounds(current_dir: str, prior_dir: str, output_path: str) -> dict:
    """Compare clause records between two rounds.

    Args:
        current_dir: path to current round's clauses/ directory
        prior_dir: path to prior round's clauses/ directory
        output_path: path to write diff-report.json

    Returns:
        dict with diff results and statistics
    """
    current_clauses = load_clauses(current_dir)
    prior_clauses = load_clauses(prior_dir)

    if not prior_clauses:
        return {
            'error': f'No prior clauses found in: {prior_dir}',
            'success': False,
        }

    diffs = match_clauses(current_clauses, prior_clauses)

    # Compute statistics
    stats = {
        'total_current': len(current_clauses),
        'total_prior': len(prior_clauses),
        'unchanged': sum(1 for d in diffs if d['diff_status'] == 'unchanged'),
        'modified': sum(1 for d in diffs if d['diff_status'] == 'modified'),
        'added': sum(1 for d in diffs if d['diff_status'] == 'added'),
        'removed': sum(1 for d in diffs if d['diff_status'] == 'removed'),
    }

    report = {
        'success': True,
        'stats': stats,
        'diffs': diffs,
    }

    # Write report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return {
        'success': True,
        'output_path': output_path,
        'stats': stats,
    }


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            'error': 'Usage: diff-rounds.py <current_clauses_dir> <prior_clauses_dir> <output_path>'
        }))
        sys.exit(1)

    result = diff_rounds(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()

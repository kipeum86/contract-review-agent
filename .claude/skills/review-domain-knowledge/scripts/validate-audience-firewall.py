#!/usr/bin/env python3
"""
Batch audience firewall validation for [EXTERNAL] comments.

Reads a comments payload, scans per-comment violations, then applies a small
set of batch heuristics for distributed leakage across the full comment set.
Writes a machine-readable firewall log to `firewall-log.json`.
"""

import sys
import os
import json
import re
from collections import defaultdict
from datetime import datetime, timezone


DIRECT_VIOLATION_PATTERNS = [
    {
        'pattern': r'\[(?:INTERNAL|PRIVILEGED)\]',
        'reason': 'internal-only marker appears in external comment',
        'category': 'internal_marker',
    },
    {
        'pattern': r'\b(?:we|our\s+team)\s+can\s+accept\b',
        'reason': 'acceptance threshold is disclosed',
        'category': 'negotiation_posture',
    },
    {
        'pattern': r'\b(?:fallback|bottom\s+line|walk[\s-]away)\b',
        'reason': 'fallback or bottom-line language is disclosed',
        'category': 'negotiation_posture',
    },
    {
        'pattern': r'\b(?:if\s+they\s+push\s+back|if\s+rejected)\b',
        'reason': 'fallback branch is disclosed',
        'category': 'negotiation_posture',
    },
    {
        'pattern': r'\b(?:our|client(?:\'s)?)\s+(?:top\s+priority|priority|priorities)\b',
        'reason': 'internal priority is disclosed',
        'category': 'priority',
    },
    {
        'pattern': r'\bleverage\b',
        'reason': 'leverage discussion appears in external comment',
        'category': 'leverage',
    },
    {
        'pattern': r'\b(?:counterparty|they)\s+(?:will|would|may|probably)\s+(?:accept|reject|push\s+back)\b',
        'reason': 'counterparty behavior assessment is disclosed',
        'category': 'counterparty_assessment',
    },
    {
        'pattern': r'\b(?:budget|authority|authorized)\s+(?:cap|limit|max(?:imum)?)\b',
        'reason': 'budget or authority limit is disclosed',
        'category': 'authority_limit',
    },
    {
        'pattern': r'\b(?:close|sign)\s+by\b',
        'reason': 'time pressure is disclosed',
        'category': 'time_pressure',
    },
    {
        'pattern': r'\b(?:as\s+discussed|per\s+our\s+(?:call|discussion|email|conversation))\b',
        'reason': 'internal discussion history is disclosed',
        'category': 'discussion_history',
    },
    {
        'pattern': r'파트너와\s*상의한\s*대로',
        'reason': 'internal discussion history is disclosed (Korean)',
        'category': 'discussion_history',
    },
    {
        'pattern': r'(?:우리\s*(?:측|쪽)?\s*)?\d+\s*개월까지는\s*수용\s*가능',
        'reason': 'acceptance threshold is disclosed (Korean)',
        'category': 'negotiation_posture',
    },
    {
        'pattern': r'우리\s*(?:측|쪽)?\s*(?:에서는|입장에서는)?\s*수용\s*가능',
        'reason': 'acceptance posture is disclosed (Korean)',
        'category': 'negotiation_posture',
    },
    {
        'pattern': r'(?:마지노선|최소\s*조건)',
        'reason': 'bottom-line language is disclosed (Korean)',
        'category': 'negotiation_posture',
    },
    {
        'pattern': r'(?:우리\s*(?:측|쪽)?\s*우선순위|최우선\s*사항)',
        'reason': 'internal priority is disclosed (Korean)',
        'category': 'priority',
    },
    {
        'pattern': r'상대방이\s*(?:받아들일|거절할|밀어붙일)\s*것',
        'reason': 'counterparty behavior assessment is disclosed (Korean)',
        'category': 'counterparty_assessment',
    },
]

DISTRIBUTED_SIGNAL_PATTERNS = [
    {
        'pattern': r'(?:'
                   r'(?:market|industry)\s+standard.{0,40}(?:\d+\s*[- ]?\s*(?:day|days|month|months|year|years)|range)'
                   r'|'
                   r'\d+\s*[- ]?\s*(?:day|days|month|months|year|years).{0,40}(?:market|industry)\s+standard'
                   r')',
        'category': 'market_range',
    },
    {
        'pattern': r'(?:'
                   r'(?:시장\s*관행|통상적(?:으로)?).{0,40}(?:\d+\s*(?:일|개월|년)|범위)'
                   r'|'
                   r'\d+\s*(?:일|개월|년).{0,40}(?:시장\s*관행|통상적(?:으로)?)'
                   r')',
        'category': 'market_range',
    },
    {
        'pattern': r'(?:aligns?\s+with\s+our\s+expectations|within\s+our\s+range|works?\s+for\s+us)',
        'category': 'acceptance_alignment',
    },
    {
        'pattern': r'(?:우리\s*기대에\s*부합|우리\s*기준에\s*맞|이\s*정도면\s*무방)',
        'category': 'acceptance_alignment',
    },
    {
        'pattern': r'(?:top\s+priority|must[\s-]?have|nice[\s-]?to[\s-]?have)',
        'category': 'priority_alignment',
    },
    {
        'pattern': r'(?:최우선|우선\s*검토|양보\s*가능)',
        'category': 'priority_alignment',
    },
]


def now_iso() -> str:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_json(path: str):
    """Load a JSON file."""
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def normalize_comment_records(payload, source_label: str) -> list[dict]:
    """Normalize comment payloads into clause-scoped records."""
    records = []

    if isinstance(payload, dict):
        if 'comments' in payload and isinstance(payload['comments'], list):
            for item in payload['comments']:
                records.extend(normalize_comment_records(item, source_label))
            return records

        if 'clause_id' in payload:
            clause_id = payload.get('clause_id') or payload.get('id') or os.path.basename(source_label)
            external_comment = (
                payload.get('external_comment')
                or payload.get('external')
                or payload.get('externalComment')
            )
            if external_comment:
                records.append({
                    'clause_id': clause_id,
                    'external_comment': str(external_comment),
                    'source': source_label,
                })
            return records

        for clause_id, value in payload.items():
            if not isinstance(value, dict):
                continue
            external_comment = (
                value.get('external_comment')
                or value.get('external')
                or value.get('externalComment')
            )
            if not external_comment:
                continue
            records.append({
                'clause_id': clause_id,
                'external_comment': str(external_comment),
                'source': source_label,
            })
        return records

    if isinstance(payload, list):
        for item in payload:
            records.extend(normalize_comment_records(item, source_label))

    return records


def load_comment_records(source_path: str) -> list[dict]:
    """Load comment records from a JSON file or a directory of JSON files."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    if os.path.isfile(source_path):
        return normalize_comment_records(load_json(source_path), source_path)

    records = []
    for dirpath, _, filenames in os.walk(source_path):
        for filename in sorted(filenames):
            if not filename.endswith('.json') or filename == 'firewall-log.json':
                continue
            file_path = os.path.join(dirpath, filename)
            records.extend(normalize_comment_records(load_json(file_path), file_path))
    return records


def scan_patterns(text: str, pattern_specs: list[dict]) -> list[dict]:
    """Scan text against pattern specs and return all matches."""
    hits = []
    for pattern_spec in pattern_specs:
        for match in re.finditer(pattern_spec['pattern'], text, re.IGNORECASE):
            hits.append({
                'category': pattern_spec['category'],
                'reason': pattern_spec.get('reason', pattern_spec['category']),
                'matched_text': match.group(),
            })
    return hits


def add_violation(violations: list[dict], clause_id: str, reason: str, scope: str, category: str, matched_text: str | None = None):
    """Append a normalized violation record."""
    violation = {
        'clause_id': clause_id,
        'reason': reason,
        'scope': scope,
        'category': category,
    }
    if matched_text:
        violation['matched_text'] = matched_text
    violations.append(violation)


def detect_distributed_leakage(records: list[dict]) -> list[dict]:
    """Detect leakage that becomes visible only across multiple comments."""
    signal_records = defaultdict(list)

    for record in records:
        hits = scan_patterns(record['external_comment'], DISTRIBUTED_SIGNAL_PATTERNS)
        seen_categories = set()
        for hit in hits:
            category = hit['category']
            if category in seen_categories:
                continue
            seen_categories.add(category)
            signal_records[category].append({
                'clause_id': record['clause_id'],
                'matched_text': hit['matched_text'],
            })

    violations = []

    market_range_records = {record['clause_id']: record for record in signal_records['market_range']}
    acceptance_records = {record['clause_id']: record for record in signal_records['acceptance_alignment']}
    if market_range_records and acceptance_records:
        implicated_clause_ids = sorted(set(market_range_records) | set(acceptance_records))
        for clause_id in implicated_clause_ids:
            add_violation(
                violations,
                clause_id=clause_id,
                reason='distributed leakage: market-range comment and acceptance-alignment comment reveal negotiating range when read together',
                scope='batch',
                category='distributed_leakage',
                matched_text=(
                    market_range_records.get(clause_id, acceptance_records.get(clause_id))['matched_text']
                ),
            )

    priority_records = {record['clause_id']: record for record in signal_records['priority_alignment']}
    if len(priority_records) >= 2:
        for clause_id, record in sorted(priority_records.items()):
            add_violation(
                violations,
                clause_id=clause_id,
                reason='distributed leakage: multiple external comments expose internal priority ordering',
                scope='batch',
                category='distributed_leakage',
                matched_text=record['matched_text'],
            )

    return violations


def default_output_path(source_path: str) -> str:
    """Derive the default firewall log path."""
    if os.path.isdir(source_path):
        return os.path.join(source_path, 'firewall-log.json')
    return os.path.join(os.path.dirname(source_path), 'firewall-log.json')


def validate_audience_firewall(source_path: str, output_path: str | None = None) -> dict:
    """Validate external comments and write a machine-readable firewall log."""
    records = load_comment_records(source_path)
    output_path = output_path or default_output_path(source_path)

    violations = []
    for record in records:
        for hit in scan_patterns(record['external_comment'], DIRECT_VIOLATION_PATTERNS):
            add_violation(
                violations,
                clause_id=record['clause_id'],
                reason=hit['reason'],
                scope='per_comment',
                category=hit['category'],
                matched_text=hit['matched_text'],
            )

    existing_keys = {
        (violation['clause_id'], violation['reason'], violation['scope'], violation['category'])
        for violation in violations
    }
    for violation in detect_distributed_leakage(records):
        key = (
            violation['clause_id'],
            violation['reason'],
            violation['scope'],
            violation['category'],
        )
        if key in existing_keys:
            continue
        violations.append(violation)
        existing_keys.add(key)

    log_payload = {
        'status': 'passed' if not violations else 'manual_required',
        'checked_at': now_iso(),
        'source': source_path,
        'external_comments_checked': len(records),
    }

    if violations:
        log_payload['manual_required_count'] = len(violations)
        log_payload['violations'] = violations

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as handle:
        json.dump(log_payload, handle, indent=2, ensure_ascii=False)

    log_payload['output_path'] = output_path
    return log_payload


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'error': 'Usage: validate-audience-firewall.py <comments.json_or_dir> [firewall-log.json]'
        }))
        sys.exit(1)

    output_path = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        result = validate_audience_firewall(sys.argv[1], output_path)
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result['status'] != 'passed':
        sys.exit(2)


if __name__ == '__main__':
    main()

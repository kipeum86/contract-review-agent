#!/usr/bin/env python3
"""
Privileged content pattern detection.
Scans document text for internal comments, strategy notes, or privileged
content that should not appear in library assets without isolation.
"""

import sys
import os
import json
import re
from collections import Counter

SCATTER_FINDING_THRESHOLD = 6
SCATTER_LINE_THRESHOLD = 4
SCATTER_RATIO_THRESHOLD = 0.2
SCATTER_CATEGORY_THRESHOLD = 3


# Patterns indicating privileged or internal content.
# Direct markers are treated the same as before, but the set now also catches
# realistic negotiation posture language that often appears without explicit tags.
PRIVILEGE_PATTERNS = [
    # English: explicit privilege / distribution markers
    {
        'pattern': r'\[INTERNAL\]',
        'description': 'Internal marker found',
        'category': 'internal_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'\[PRIVILEGED\]',
        'description': 'Privileged marker found',
        'category': 'privilege_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'\[CONFIDENTIAL\s*[-–—]\s*ATTORNEY',
        'description': 'Attorney-client privilege marker',
        'category': 'privilege_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'attorney[\s-]client\s+privilege',
        'description': 'Attorney-client privilege reference',
        'category': 'privilege_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'work[\s-]product\s+(?:doctrine|privilege)',
        'description': 'Work product doctrine reference',
        'category': 'privilege_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'do\s+not\s+(?:share|distribute|forward|disclose)\s+(?:externally|outside)',
        'description': 'Distribution restriction',
        'category': 'distribution_limit',
        'severity': 'hard',
    },
    {
        'pattern': r'internal\s+(?:use\s+)?only',
        'description': 'Internal use only marker',
        'category': 'distribution_limit',
        'severity': 'hard',
    },
    {
        'pattern': r'not\s+for\s+(?:external|public)\s+(?:use|distribution|disclosure)',
        'description': 'External restriction',
        'category': 'distribution_limit',
        'severity': 'hard',
    },
    {
        'pattern': r'draft\s*[-–—]\s*(?:not\s+for\s+circulation|internal)',
        'description': 'Draft restriction',
        'category': 'distribution_limit',
        'severity': 'hard',
    },
    {
        'pattern': r'negotiation\s+strategy',
        'description': 'Negotiation strategy reference',
        'category': 'strategy',
        'severity': 'hard',
    },
    {
        'pattern': r'our\s+(?:bottom\s+line|fallback|walk[\s-]away)',
        'description': 'Internal negotiation position',
        'category': 'negotiation_posture',
        'severity': 'hard',
    },
    {
        'pattern': r'leverage\s+position',
        'description': 'Leverage discussion',
        'category': 'leverage',
        'severity': 'hard',
    },

    # English: indirect negotiation posture / acceptance language
    {
        'pattern': r'as\s+(?:previously\s+)?discussed(?:\s+(?:with|on|during)\b.{0,80})?',
        'description': 'Indirect negotiation history reference',
        'category': 'discussion_history',
        'severity': 'soft',
    },
    {
        'pattern': r'per\s+our\s+(?:call|discussion|conversation|email|notes?)',
        'description': 'Internal discussion reference',
        'category': 'discussion_history',
        'severity': 'soft',
    },
    {
        'pattern': r'(?:we|our\s+team)\s+can\s+accept\b',
        'description': 'Acceptance threshold language',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'acceptable\s+(?:if|for\s+us|on\s+our\s+side)',
        'description': 'Conditional acceptance language',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'we\s+(?:could|can)\s+(?:live|work)\s+with\b',
        'description': 'Fallback posture language',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'(?:our|client(?:\'s)?)\s+(?:top\s+priority|priority|priorities)',
        'description': 'Internal priority reference',
        'category': 'priority',
        'severity': 'soft',
    },
    {
        'pattern': r'(?:if\s+they\s+push\s+back|if\s+rejected)',
        'description': 'Fallback branch reference',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'counterpart(?:y|ies)\s+(?:will|would|may|probably)\s+(?:accept|reject|push\s+back)',
        'description': 'Counterparty behavior assessment',
        'category': 'counterparty_assessment',
        'severity': 'soft',
    },
    {
        'pattern': r'within\s+our\s+(?:range|comfort\s+zone|authority)',
        'description': 'Internal authority or comfort range reference',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },

    # Korean: explicit privilege / distribution markers
    {
        'pattern': r'내부\s*(?:전용|용도|문서)',
        'description': 'Internal-only marker (Korean)',
        'category': 'internal_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'대외비',
        'description': 'Confidential marker (Korean)',
        'category': 'privilege_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'비밀\s*유지\s*특권',
        'description': 'Privilege marker (Korean)',
        'category': 'privilege_marker',
        'severity': 'hard',
    },
    {
        'pattern': r'외부\s*(?:공유|배포)\s*(?:금지|불가)',
        'description': 'External distribution prohibition (Korean)',
        'category': 'distribution_limit',
        'severity': 'hard',
    },
    {
        'pattern': r'협상\s*전략',
        'description': 'Negotiation strategy (Korean)',
        'category': 'strategy',
        'severity': 'hard',
    },
    {
        'pattern': r'우리\s*(?:측|쪽)\s*(?:마지노선|최소\s*조건)',
        'description': 'Internal negotiation position (Korean)',
        'category': 'negotiation_posture',
        'severity': 'hard',
    },

    # Korean: indirect negotiation posture / acceptance language
    {
        'pattern': r'파트너와\s*상의한\s*대로',
        'description': 'Internal discussion history reference (Korean)',
        'category': 'discussion_history',
        'severity': 'soft',
    },
    {
        'pattern': r'논의한\s*바(?:와\s*같이)?',
        'description': 'Discussion history reference (Korean)',
        'category': 'discussion_history',
        'severity': 'soft',
    },
    {
        'pattern': r'우리\s*(?:측|쪽)?\s*(?:에서는|입장에서는)?\s*수용\s*가능',
        'description': 'Acceptance threshold language (Korean)',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'\d+\s*개월까지는\s*수용\s*가능',
        'description': 'Quantified acceptance threshold (Korean)',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'이\s*선에서는\s*수용',
        'description': 'Fallback posture language (Korean)',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'양보\s*가능',
        'description': 'Concession language (Korean)',
        'category': 'negotiation_posture',
        'severity': 'soft',
    },
    {
        'pattern': r'(?:우리\s*(?:측|쪽)?\s*우선순위|최우선\s*사항)',
        'description': 'Priority reference (Korean)',
        'category': 'priority',
        'severity': 'soft',
    },
    {
        'pattern': r'딜브레이커',
        'description': 'Dealbreaker reference (Korean)',
        'category': 'priority',
        'severity': 'soft',
    },
]


def scan_for_privilege(text: str) -> list[dict]:
    """Scan text for privileged content patterns.

    Returns list of matches with pattern, description, and location info.
    """
    findings = []
    lines = text.split('\n')

    for line_no, line in enumerate(lines, 1):
        for pattern_spec in PRIVILEGE_PATTERNS:
            pattern = pattern_spec['pattern']
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for match in matches:
                findings.append({
                    'line': line_no,
                    'column': match.start(),
                    'matched_text': match.group(),
                    'context': line.strip()[:200],
                    'pattern': pattern,
                    'description': pattern_spec['description'],
                    'category': pattern_spec['category'],
                    'severity': pattern_spec['severity'],
                })

    return findings


def summarize_findings(findings: list[dict], total_lines: int) -> dict:
    """Summarize findings to assess whether privileged content is scattered."""
    unique_lines = sorted({finding['line'] for finding in findings})
    unique_line_count = len(unique_lines)
    categories = Counter(finding['category'] for finding in findings)
    severity_counts = Counter(finding['severity'] for finding in findings)
    line_coverage_ratio = (
        unique_line_count / max(total_lines, 1)
        if total_lines
        else 0.0
    )

    scatter_indicators = []
    if len(findings) >= SCATTER_FINDING_THRESHOLD:
        scatter_indicators.append('finding_count')
    if unique_line_count >= SCATTER_LINE_THRESHOLD:
        scatter_indicators.append('line_count')
    if unique_line_count >= 3 and line_coverage_ratio >= SCATTER_RATIO_THRESHOLD:
        scatter_indicators.append('line_coverage_ratio')
    if len(categories) >= SCATTER_CATEGORY_THRESHOLD and len(findings) >= 4:
        scatter_indicators.append('category_diversity')

    scatter_score = len(scatter_indicators)

    return {
        'line_count': total_lines,
        'unique_line_count': unique_line_count,
        'line_coverage_ratio': round(line_coverage_ratio, 4),
        'categories': dict(categories),
        'severity_counts': dict(severity_counts),
        'scatter_indicators': scatter_indicators,
        'scatter_score': scatter_score,
        'can_isolate': scatter_score < 2,
    }


def check_file(file_path: str) -> dict:
    """Check a single file for privileged content.

    Returns:
        dict with:
          - file: file path
          - findings: list of matches
          - has_privilege: bool
          - can_isolate: bool (whether privileged sections can be cleanly separated)
    """
    result = {
        'file': file_path,
        'findings': [],
        'has_privilege': False,
        'can_isolate': True,
        'isolation_analysis': {},
        'error': None,
    }

    if not os.path.exists(file_path):
        result['error'] = f"File not found: {file_path}"
        return result

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except IOError as e:
        result['error'] = str(e)
        return result

    findings = scan_for_privilege(text)
    result['findings'] = findings
    result['has_privilege'] = len(findings) > 0

    isolation_analysis = summarize_findings(findings, len(text.splitlines()))
    result['isolation_analysis'] = isolation_analysis
    result['can_isolate'] = isolation_analysis['can_isolate']

    return result


def check_package(package_dir: str) -> dict:
    """Check all text files in a package for privileged content."""
    results = {
        'package_dir': package_dir,
        'files_checked': 0,
        'files_with_privilege': 0,
        'total_findings': 0,
        'can_isolate_all': True,
        'severity_counts': {},
        'file_results': [],
    }

    if not os.path.isdir(package_dir):
        results['error'] = f"Directory not found: {package_dir}"
        return results

    # Check normalized text files
    for dirpath, _, filenames in os.walk(package_dir):
        for fn in filenames:
            if fn.endswith(('.md', '.txt', '.json', '.yaml', '.yml')):
                fp = os.path.join(dirpath, fn)
                file_result = check_file(fp)
                results['files_checked'] += 1
                if file_result['has_privilege']:
                    results['files_with_privilege'] += 1
                    results['total_findings'] += len(file_result['findings'])
                    if not file_result['can_isolate']:
                        results['can_isolate_all'] = False
                results['file_results'].append(file_result)

    severity_counts = Counter()
    for file_result in results['file_results']:
        for finding in file_result.get('findings', []):
            severity_counts[finding.get('severity', 'unknown')] += 1

    results['severity_counts'] = dict(severity_counts)

    return results


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: check-privilege-leak.py <file_or_dir>'}))
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isdir(target):
        result = check_package(target)
    else:
        result = check_file(target)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit codes:
    # 0 = clean
    # 1 = error
    # 2 = privilege found but isolable
    # 3 = privilege found and cannot isolate (hard fail)
    if result.get('error'):
        sys.exit(1)
    if isinstance(result.get('can_isolate_all'), bool) and not result['can_isolate_all']:
        sys.exit(3)
    if result.get('has_privilege') or result.get('files_with_privilege', 0) > 0:
        sys.exit(2)


if __name__ == '__main__':
    main()

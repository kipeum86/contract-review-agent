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

# Patterns indicating privileged or internal content
PRIVILEGE_PATTERNS = [
    # English patterns
    (r'\[INTERNAL\]', 'Internal marker found'),
    (r'\[PRIVILEGED\]', 'Privileged marker found'),
    (r'\[CONFIDENTIAL\s*[-–—]\s*ATTORNEY', 'Attorney-client privilege marker'),
    (r'attorney[\s-]client\s+privilege', 'Attorney-client privilege reference'),
    (r'work[\s-]product\s+(doctrine|privilege)', 'Work product doctrine reference'),
    (r'(?i)do\s+not\s+(share|distribute|forward|disclose)\s+(externally|outside)', 'Distribution restriction'),
    (r'(?i)internal\s+(use\s+)?only', 'Internal use only marker'),
    (r'(?i)not\s+for\s+(external|public)\s+(use|distribution|disclosure)', 'External restriction'),
    (r'(?i)draft\s*[-–—]\s*(not\s+for\s+circulation|internal)', 'Draft restriction'),
    (r'(?i)negotiation\s+strategy', 'Negotiation strategy reference'),
    (r'(?i)our\s+(bottom\s+line|fallback|walk[\s-]away)', 'Internal negotiation position'),
    (r'(?i)leverage\s+position', 'Leverage discussion'),

    # Korean patterns
    (r'내부\s*(전용|용도|문서)', 'Internal-only marker (Korean)'),
    (r'대외비', 'Confidential marker (Korean)'),
    (r'비밀\s*유지\s*특권', 'Privilege marker (Korean)'),
    (r'외부\s*(공유|배포)\s*(금지|불가)', 'External distribution prohibition (Korean)'),
    (r'협상\s*전략', 'Negotiation strategy (Korean)'),
    (r'우리\s*(측|쪽)\s*(마지노선|최소\s*조건)', 'Internal negotiation position (Korean)'),
]


def scan_for_privilege(text: str) -> list[dict]:
    """Scan text for privileged content patterns.

    Returns list of matches with pattern, description, and location info.
    """
    findings = []
    lines = text.split('\n')

    for line_no, line in enumerate(lines, 1):
        for pattern, description in PRIVILEGE_PATTERNS:
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for match in matches:
                findings.append({
                    'line': line_no,
                    'column': match.start(),
                    'matched_text': match.group(),
                    'context': line.strip()[:200],
                    'pattern': pattern,
                    'description': description,
                })

    return findings


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

    # Simple heuristic: if privileged content is scattered throughout (>5 locations),
    # it's hard to isolate
    if len(findings) > 5:
        result['can_isolate'] = False

    return result


def check_package(package_dir: str) -> dict:
    """Check all text files in a package for privileged content."""
    results = {
        'package_dir': package_dir,
        'files_checked': 0,
        'files_with_privilege': 0,
        'total_findings': 0,
        'can_isolate_all': True,
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

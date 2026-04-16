#!/usr/bin/env python3
"""
Extract tracked changes (redlines) and comments from a DOCX file.

This is the inverse of apply-redlines.py and apply-comments.py: where those
scripts write OOXML tracked changes into a DOCX, this script reads them out
and produces structured JSON.

Usage:
    extract-redlines.py <input.docx> <output_dir>

Outputs:
    <output_dir>/changes.json           — All tracked changes (ins/del/replacement)
    <output_dir>/comments.json          — All margin comments
    <output_dir>/redline_audit.json     — Prompt-injection audit trail
    <output_dir>/extraction-report.json — Statistics
    <output_dir>/original.md            — Pre-edit text (all changes rejected)
"""

import sys
import os
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ── OOXML namespace map (shared with apply-redlines.py / apply-comments.py) ──

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
}

for prefix, uri in NSMAP.items():
    ET.register_namespace(prefix, uri)

W = NSMAP['w']


# ── Utility functions (mirrored from apply-redlines.py) ──

def local_name(tag: str) -> str:
    """Return the local name of an XML tag."""
    return tag.split('}')[-1] if '}' in tag else tag


def get_attr_local(element: ET.Element, attr_name: str) -> str | None:
    """Read an attribute by local name regardless of namespace."""
    for key, value in element.attrib.items():
        if key == attr_name or key.endswith(f'}}{attr_name}'):
            return value
    return None


# ── Prompt-injection sanitization ──

_PROMPT_INJECTION_PATTERNS = [
    # Role marker tokens (exact)
    r'\[(?:SYSTEM|ASSISTANT|USER|IGNORE|OVERRIDE|MANUAL_REQUIRED|PRIVILEGED)\]',
    # Audience-firewall tokens that may be forged inside a counterparty comment
    r'\[(?:INTERNAL|EXTERNAL)\]',
    # XML-ish role tags
    r'<\s*/?\s*(?:system|user|assistant|untrusted_contract_content|instruction|instructions)\s*>',
    # English jailbreak phrases
    r'(?i)ignore\s+(?:the\s+)?(?:previous|prior|above|all)\s+(?:instructions?|prompts?)',
    r'(?i)disregard\s+(?:the\s+)?(?:previous|prior|above|all)',
    r'(?i)system\s+override',
    r'(?i)you\s+are\s+now\s+(?:a|an|the)\s+',
    r'(?i)forget\s+(?:your|all|the)\s+(?:instructions?|prompts?|rules?)',
    r'(?i)new\s+instructions?\s*:',
    # Korean jailbreak phrases
    r'이전\s*지시(?:사항)?(?:을|를)?\s*(?:무시|잊)',
    r'이제부터\s+(?:너는|당신은)',
    r'앞(?:의|에)\s*(?:지시|명령)(?:을|를)?\s*무시',
]
_COMPILED_PI_PATTERNS = [re.compile(pattern) for pattern in _PROMPT_INJECTION_PATTERNS]
_MAX_SANITIZE_LENGTH = 200_000  # catastrophic backtracking guard


def _sanitize_untrusted_text(text: str, context: str = '') -> tuple[str, list[dict]]:
    """Escape prompt-injection tokens in untrusted DOCX text."""
    if not text or len(text) > _MAX_SANITIZE_LENGTH:
        return text, []

    matches = []
    for regex in _COMPILED_PI_PATTERNS:
        for match in regex.finditer(text):
            matches.append({
                'pattern': regex.pattern,
                'match': match.group(0),
                'start': match.start(),
                'end': match.end(),
                'context': context,
            })

    if not matches:
        return text, []

    sanitized = text
    for match in sorted(matches, key=lambda item: (-item['start'], -(item['end'] - item['start']))):
        escaped = f'`<escape>{match["match"]}</escape>`'
        sanitized = sanitized[:match['start']] + escaped + sanitized[match['end']:]

    return sanitized, matches


# ── Text extraction helpers ──

def run_text_content(run: ET.Element) -> str:
    """Extract text from a single run element."""
    parts = []
    for child in run:
        name = local_name(child.tag)
        if name in ('t', 'delText'):
            parts.append(child.text or '')
        elif name == 'tab':
            parts.append('\t')
        elif name in ('br', 'cr'):
            parts.append('\n')
    return ''.join(parts)


def element_all_text(elem: ET.Element) -> str:
    """Recursively extract all text from an element and its descendants."""
    parts = []
    for run in elem.iter(f'{{{W}}}r'):
        parts.append(run_text_content(run))
    return ''.join(parts)


def _flush_pending_deletion(changes: list[dict], pending_deletion: dict | None) -> None:
    """Append a pending deletion to changes, removing transient bookkeeping."""
    if pending_deletion is None:
        return
    pending_deletion.pop('_change_index', None)
    changes.append(pending_deletion)


# ── Core extraction ──

def extract_changes_from_body(body: ET.Element) -> tuple[list[dict], list[str], list[str]]:
    """Walk all paragraphs and extract tracked changes.

    Returns:
        changes: list of change records
        original_lines: paragraph texts with all changes rejected (pre-edit)
        accepted_lines: paragraph texts with all changes accepted (post-edit)
    """
    changes = []
    original_lines = []
    accepted_lines = []
    change_counter = 0

    paragraphs = list(body.iter(f'{{{W}}}p'))

    for para_idx, para in enumerate(paragraphs):
        original_parts = []   # text with changes rejected
        accepted_parts = []   # text with changes accepted
        pending_deletion = None  # for replacement detection

        for child in para:
            name = local_name(child.tag)

            if name == 'r':
                # Normal (unchanged) run
                text = run_text_content(child)
                original_parts.append(text)
                accepted_parts.append(text)

                # Flush any pending deletion that wasn't followed by an insertion
                if pending_deletion is not None:
                    _flush_pending_deletion(changes, pending_deletion)
                    pending_deletion = None

            elif name == 'del':
                author = get_attr_local(child, 'author') or ''
                date = get_attr_local(child, 'date') or ''
                change_index = change_counter
                deleted_text_raw = element_all_text(child)
                deleted_text, del_matches = _sanitize_untrusted_text(
                    deleted_text_raw,
                    context=f'change[{change_index}].deleted_text',
                )

                original_parts.append(deleted_text)
                # Do NOT add to accepted_parts (it's deleted)

                # Hold as pending — if next sibling is w:ins from same author,
                # merge into a replacement
                pending_deletion = {
                    'change_id': f'chg-{change_index:03d}',
                    'type': 'deletion',
                    'revision_id': get_attr_local(child, 'id') or '',
                    'author': author,
                    'date': date,
                    'paragraph_index': para_idx,
                    'text': deleted_text,
                    'context_before': ''.join(original_parts[:-1])[-40:] if original_parts[:-1] else '',
                    'context_after': '',  # filled later
                    'sanitize_matches': del_matches,
                    '_change_index': change_index,
                }
                change_counter += 1

            elif name == 'ins':
                author = get_attr_local(child, 'author') or ''
                date = get_attr_local(child, 'date') or ''

                if pending_deletion is not None and pending_deletion['author'] == author:
                    change_index = pending_deletion.get('_change_index', change_counter)
                    inserted_text_raw = element_all_text(child)
                    inserted_text, ins_matches = _sanitize_untrusted_text(
                        inserted_text_raw,
                        context=f'change[{change_index}].inserted_text',
                    )
                else:
                    change_index = change_counter
                    inserted_text_raw = element_all_text(child)
                    inserted_text, ins_matches = _sanitize_untrusted_text(
                        inserted_text_raw,
                        context=f'change[{change_index}].text',
                    )

                accepted_parts.append(inserted_text)
                # Do NOT add to original_parts (it was inserted)

                if pending_deletion is not None and pending_deletion['author'] == author:
                    # Merge deletion + insertion into replacement
                    # Reuse the deletion's change_id but decrement counter since
                    # we're merging two into one
                    replacement = {
                        'change_id': pending_deletion['change_id'],
                        'type': 'replacement',
                        'revision_id_del': pending_deletion['revision_id'],
                        'revision_id_ins': get_attr_local(child, 'id') or '',
                        'author': author,
                        'date': date,
                        'paragraph_index': para_idx,
                        'deleted_text': pending_deletion['text'],
                        'inserted_text': inserted_text,
                        'context_before': pending_deletion['context_before'],
                        'context_after': '',  # filled later
                        'sanitize_matches': pending_deletion.get('sanitize_matches', []) + ins_matches,
                    }
                    changes.append(replacement)
                    pending_deletion = None
                else:
                    # Flush pending deletion if any
                    if pending_deletion is not None:
                        _flush_pending_deletion(changes, pending_deletion)
                        pending_deletion = None

                    change = {
                        'change_id': f'chg-{change_counter:03d}',
                        'type': 'insertion',
                        'revision_id': get_attr_local(child, 'id') or '',
                        'author': author,
                        'date': date,
                        'paragraph_index': para_idx,
                        'text': inserted_text,
                        'context_before': ''.join(accepted_parts[:-1])[-40:] if accepted_parts[:-1] else '',
                        'context_after': '',  # filled later
                        'sanitize_matches': ins_matches,
                    }
                    changes.append(change)
                    change_counter += 1

            # Other elements (bookmarks, comments markers, etc.) — skip

        # Flush any trailing pending deletion
        if pending_deletion is not None:
            _flush_pending_deletion(changes, pending_deletion)
            pending_deletion = None

        original_lines.append(''.join(original_parts))
        accepted_lines.append(''.join(accepted_parts))

    # Fill context_after for all changes
    for change in changes:
        para_idx = change['paragraph_index']
        if change['type'] == 'replacement':
            # Use accepted text after the insertion point
            after_text = ''.join(accepted_lines[para_idx:para_idx + 1])
            inserted = change.get('inserted_text', '')
            pos = after_text.find(inserted)
            if pos >= 0 and pos + len(inserted) < len(after_text):
                change['context_after'] = after_text[pos + len(inserted):pos + len(inserted) + 40]
        elif change['type'] == 'insertion':
            after_text = ''.join(accepted_lines[para_idx:para_idx + 1])
            text = change.get('text', '')
            pos = after_text.find(text)
            if pos >= 0 and pos + len(text) < len(after_text):
                change['context_after'] = after_text[pos + len(text):pos + len(text) + 40]
        elif change['type'] == 'deletion':
            after_text = ''.join(original_lines[para_idx:para_idx + 1])
            text = change.get('text', '')
            pos = after_text.find(text)
            if pos >= 0 and pos + len(text) < len(after_text):
                change['context_after'] = after_text[pos + len(text):pos + len(text) + 40]

    return changes, original_lines, accepted_lines


def extract_comments(zip_file: zipfile.ZipFile, body: ET.Element) -> list[dict]:
    """Extract comments and map them to paragraph positions via comment range markers."""
    # Parse comments.xml
    try:
        comments_xml = zip_file.read('word/comments.xml')
    except KeyError:
        return []

    comments_root = ET.fromstring(comments_xml)
    comment_bodies = {}

    for comment_elem in comments_root.iter(f'{{{W}}}comment'):
        cid = get_attr_local(comment_elem, 'id')
        if cid is None:
            continue
        raw_text = element_all_text(comment_elem)
        sanitized_text, text_matches = _sanitize_untrusted_text(
            raw_text,
            context=f'comment[{cid}].text',
        )
        raw_author = get_attr_local(comment_elem, 'author') or ''
        sanitized_author, author_matches = _sanitize_untrusted_text(
            raw_author,
            context=f'comment[{cid}].author',
        )
        comment_bodies[cid] = {
            'comment_id': cid,
            'author': sanitized_author,
            'initials': get_attr_local(comment_elem, 'initials') or '',
            'date': get_attr_local(comment_elem, 'date') or '',
            'text': sanitized_text,
            'sanitize_matches': text_matches + author_matches,
        }

    # Map comment ranges to paragraphs
    comment_range_starts = {}  # comment_id → paragraph_index
    comment_range_ends = {}    # comment_id → paragraph_index

    paragraphs = list(body.iter(f'{{{W}}}p'))
    for para_idx, para in enumerate(paragraphs):
        for child in para:
            name = local_name(child.tag)
            if name == 'commentRangeStart':
                cid = get_attr_local(child, 'id')
                if cid:
                    comment_range_starts[cid] = para_idx
            elif name == 'commentRangeEnd':
                cid = get_attr_local(child, 'id')
                if cid:
                    comment_range_ends[cid] = para_idx

    # Build final comment records
    comments = []
    for cid, body_data in comment_bodies.items():
        start_para = comment_range_starts.get(cid)
        end_para = comment_range_ends.get(cid)

        anchor_indices = []
        anchor_snippet = ''

        if start_para is not None and end_para is not None:
            anchor_indices = list(range(start_para, end_para + 1))
            # Build snippet from anchored paragraphs
            snippet_parts = []
            for idx in anchor_indices:
                if idx < len(paragraphs):
                    text = ''
                    for run in paragraphs[idx].iter(f'{{{W}}}r'):
                        text += run_text_content(run)
                    if text.strip():
                        snippet_parts.append(text.strip())
            anchor_snippet = ' ... '.join(snippet_parts)[:120]
        elif start_para is not None:
            anchor_indices = [start_para]

        record = {
            **body_data,
            'anchor_paragraph_indices': anchor_indices,
            'anchor_text_snippet': anchor_snippet,
        }
        comments.append(record)

    # Sort by position
    comments.sort(key=lambda c: c['anchor_paragraph_indices'][0] if c['anchor_paragraph_indices'] else 999999)

    return comments


def build_extraction_report(source_file: str, changes: list[dict],
                            comments: list[dict], total_paragraphs: int) -> dict:
    """Build summary statistics."""
    insertions = [c for c in changes if c['type'] == 'insertion']
    deletions = [c for c in changes if c['type'] == 'deletion']
    replacements = [c for c in changes if c['type'] == 'replacement']

    authors = set()
    dates = []
    for c in changes:
        if c.get('author'):
            authors.add(c['author'])
        if c.get('date'):
            dates.append(c['date'])
    for c in comments:
        if c.get('author'):
            authors.add(c['author'])
        if c.get('date'):
            dates.append(c['date'])

    paras_with_changes = set(c['paragraph_index'] for c in changes)

    return {
        'success': True,
        'source_file': source_file,
        'total_paragraphs': total_paragraphs,
        'paragraphs_with_changes': len(paras_with_changes),
        'total_changes': len(changes),
        'total_insertions': len(insertions),
        'total_deletions': len(deletions),
        'total_replacements': len(replacements),
        'total_comments': len(comments),
        'unique_authors': sorted(authors),
        'date_range': {
            'earliest': min(dates) if dates else None,
            'latest': max(dates) if dates else None,
        },
    }


def lines_to_markdown(lines: list[str]) -> str:
    """Convert paragraph text lines to markdown, stripping empty lines."""
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            result.append(stripped)
        else:
            # Preserve paragraph breaks
            if result and result[-1] != '':
                result.append('')
    return '\n\n'.join(result)


# ── Main entry point ──

def extract_redlines(docx_path: str, output_dir: str) -> dict:
    """Extract all tracked changes and comments from a DOCX file.

    Args:
        docx_path: Path to the input DOCX file.
        output_dir: Directory to write output JSON files.

    Returns:
        Extraction report dict.
    """
    if not os.path.exists(docx_path):
        return {'success': False, 'error': f'File not found: {docx_path}'}

    os.makedirs(output_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(docx_path, 'r') as zf:
            # Parse document.xml
            doc_xml = zf.read('word/document.xml')
            doc_root = ET.fromstring(doc_xml)
            body = doc_root.find(f'{{{W}}}body')

            if body is None:
                return {'success': False, 'error': 'No body element in document.xml'}

            # Extract tracked changes
            changes, original_lines, accepted_lines = extract_changes_from_body(body)

            # Extract comments
            comments = extract_comments(zf, body)

    except zipfile.BadZipFile:
        return {'success': False, 'error': 'Invalid DOCX file (not a valid ZIP)'}
    except KeyError as e:
        return {'success': False, 'error': f'Missing required file in DOCX: {e}'}

    source_file = os.path.basename(docx_path)
    total_paragraphs = len(original_lines)

    # Build report
    report = build_extraction_report(source_file, changes, comments, total_paragraphs)
    all_matches = []
    for change in changes:
        all_matches.extend(change.get('sanitize_matches', []))
    for comment in comments:
        all_matches.extend(comment.get('sanitize_matches', []))
    report['prompt_injection_suspected'] = bool(all_matches)
    extracted_at = datetime.now(timezone.utc).isoformat()

    # Write changes.json
    changes_data = {
        'version': 1,
        'extracted_at': extracted_at,
        'source_file': source_file,
        'total_changes': len(changes),
        'changes': changes,
    }
    with open(os.path.join(output_dir, 'changes.json'), 'w', encoding='utf-8') as f:
        json.dump(changes_data, f, indent=2, ensure_ascii=False)

    # Write comments.json
    comments_data = {
        'version': 1,
        'extracted_at': extracted_at,
        'source_file': source_file,
        'total_comments': len(comments),
        'comments': comments,
    }
    with open(os.path.join(output_dir, 'comments.json'), 'w', encoding='utf-8') as f:
        json.dump(comments_data, f, indent=2, ensure_ascii=False)

    # Write redline_audit.json
    audit_data = {
        'version': 1,
        'extracted_at': extracted_at,
        'source_file': source_file,
        'prompt_injection_suspected': bool(all_matches),
        'total_matches': len(all_matches),
        'matches': all_matches,
    }
    with open(os.path.join(output_dir, 'redline_audit.json'), 'w', encoding='utf-8') as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)

    # Write extraction-report.json
    with open(os.path.join(output_dir, 'extraction-report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Write original.md (pre-edit text)
    original_md = lines_to_markdown(original_lines)
    with open(os.path.join(output_dir, 'original.md'), 'w', encoding='utf-8') as f:
        f.write(original_md)

    if all_matches:
        print(
            f"WARNING: {len(all_matches)} prompt-injection pattern match(es) "
            f"detected in {docx_path}. See {output_dir}/redline_audit.json. "
            f"Downstream review should treat redline_record as "
            f"prompt_injection_suspected.",
            file=sys.stderr,
        )

    return report


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            'error': 'Usage: extract-redlines.py <input.docx> <output_dir>',
            'success': False,
        }))
        sys.exit(1)

    result = extract_redlines(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()

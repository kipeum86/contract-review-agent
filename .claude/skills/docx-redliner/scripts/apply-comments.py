#!/usr/bin/env python3
"""
Apply comments to unpacked DOCX XML.

This version preserves existing comment parts instead of recreating them,
appends new comments with non-conflicting IDs, and ensures the DOCX package has
the required relationships/content-type overrides for `word/comments.xml`.
"""

import sys
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}
REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
COMMENTS_REL_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments'
COMMENTS_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml'

for prefix, uri in NSMAP.items():
    ET.register_namespace(prefix, uri)
ET.register_namespace('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006')
ET.register_namespace('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing')

DEFAULT_AUTHOR = 'Reviewer'
DEFAULT_INITIALS = 'RV'
FAILURE_RATE_THRESHOLD = 0.10


def local_name(tag: str) -> str:
    """Return the local name of a tag without namespace."""
    return tag.split('}')[-1] if '}' in tag else tag


def get_attr_local(element: ET.Element, attr_name: str) -> str | None:
    """Read an attribute by local name regardless of namespace."""
    for key, value in element.attrib.items():
        if key == attr_name or key.endswith(f'}}{attr_name}'):
            return value
    return None


def next_comment_id(root: ET.Element) -> int:
    """Return the next available comment ID."""
    max_id = 0
    for comment in root.findall(f'{{{NSMAP["w"]}}}comment'):
        comment_id = get_attr_local(comment, 'id')
        if comment_id is None:
            continue
        try:
            max_id = max(max_id, int(comment_id))
        except ValueError:
            continue
    return max_id + 1


def load_comments_root(comments_xml_path: str) -> tuple[ET.ElementTree, ET.Element]:
    """Load existing comments.xml or create a new comments root."""
    if os.path.exists(comments_xml_path):
        tree = ET.parse(comments_xml_path)
        return tree, tree.getroot()

    root = ET.Element(f'{{{NSMAP["w"]}}}comments')
    tree = ET.ElementTree(root)
    return tree, root


def create_comment_element(comment: dict) -> ET.Element:
    """Create a Word comment element."""
    w = NSMAP['w']
    c_elem = ET.Element(f'{{{w}}}comment')
    c_elem.set(f'{{{w}}}id', str(comment['id']))
    c_elem.set(f'{{{w}}}author', comment.get('author', DEFAULT_AUTHOR))
    c_elem.set(f'{{{w}}}date', comment.get('date', ''))
    c_elem.set(f'{{{w}}}initials', comment.get('initials', DEFAULT_INITIALS))

    p_elem = ET.SubElement(c_elem, f'{{{w}}}p')
    r_elem = ET.SubElement(p_elem, f'{{{w}}}r')
    t_elem = ET.SubElement(r_elem, f'{{{w}}}t')
    t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t_elem.text = comment['text']

    return c_elem


def append_comments_xml(comments: list[dict], output_path: str) -> dict:
    """Append comments to an existing comments.xml without destroying prior entries."""
    tree, root = load_comments_root(output_path)

    for comment in comments:
        root.append(create_comment_element(comment))

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    return {
        'comments_xml_path': output_path,
        'comments_added': len(comments),
        'starting_comment_id': comments[0]['id'] if comments else None,
        'ending_comment_id': comments[-1]['id'] if comments else None,
    }


def ensure_comments_relationship(unpacked_dir: str) -> bool:
    """Ensure document.xml.rels contains a relationship to comments.xml."""
    rels_path = os.path.join(unpacked_dir, 'word', '_rels', 'document.xml.rels')
    os.makedirs(os.path.dirname(rels_path), exist_ok=True)

    if os.path.exists(rels_path):
        tree = ET.parse(rels_path)
        root = tree.getroot()
    else:
        root = ET.Element(f'{{{REL_NS}}}Relationships')
        tree = ET.ElementTree(root)

    for rel in root.findall(f'{{{REL_NS}}}Relationship'):
        if rel.get('Type') == COMMENTS_REL_TYPE:
            return False

    existing_ids = {
        rel.get('Id')
        for rel in root.findall(f'{{{REL_NS}}}Relationship')
        if rel.get('Id')
    }
    next_index = 1
    while f'rIdComments{next_index}' in existing_ids:
        next_index += 1

    rel = ET.SubElement(root, f'{{{REL_NS}}}Relationship')
    rel.set('Id', f'rIdComments{next_index}')
    rel.set('Type', COMMENTS_REL_TYPE)
    rel.set('Target', 'comments.xml')

    tree.write(rels_path, encoding='UTF-8', xml_declaration=True)
    return True


def ensure_comments_content_type(unpacked_dir: str) -> bool:
    """Ensure [Content_Types].xml contains the comments.xml override."""
    content_types_path = os.path.join(unpacked_dir, '[Content_Types].xml')
    if not os.path.exists(content_types_path):
        return False

    tree = ET.parse(content_types_path)
    root = tree.getroot()
    for override in root.findall(f'{{{CONTENT_TYPES_NS}}}Override'):
        if override.get('PartName') == '/word/comments.xml':
            return False

    override = ET.SubElement(root, f'{{{CONTENT_TYPES_NS}}}Override')
    override.set('PartName', '/word/comments.xml')
    override.set('ContentType', COMMENTS_CONTENT_TYPE)
    tree.write(content_types_path, encoding='UTF-8', xml_declaration=True)
    return True


def first_direct_run_index(paragraph: ET.Element) -> int:
    """Return the index of the first direct run child in a paragraph."""
    for index, child in enumerate(list(paragraph)):
        if local_name(child.tag) == 'r':
            return index
    return len(list(paragraph))


def last_direct_run_index(paragraph: ET.Element) -> int:
    """Return the index of the last direct run child in a paragraph."""
    children = list(paragraph)
    for index in range(len(children) - 1, -1, -1):
        if local_name(children[index].tag) == 'r':
            return index
    return -1


def make_comment_reference_run(comment_id: int) -> ET.Element:
    """Create a run containing a commentReference."""
    w = NSMAP['w']
    ref_run = ET.Element(f'{{{w}}}r')
    r_pr = ET.SubElement(ref_run, f'{{{w}}}rPr')
    r_style = ET.SubElement(r_pr, f'{{{w}}}rStyle')
    r_style.set(f'{{{w}}}val', 'CommentReference')
    comment_ref = ET.SubElement(ref_run, f'{{{w}}}commentReference')
    comment_ref.set(f'{{{w}}}id', str(comment_id))
    return ref_run


def paragraph_has_comment_reference(paragraph: ET.Element, comment_id: int) -> bool:
    """Return True if the paragraph already references the given comment ID."""
    for child in paragraph:
        if local_name(child.tag) != 'r':
            continue
        for sub in child:
            if local_name(sub.tag) == 'commentReference' and get_attr_local(sub, 'id') == str(comment_id):
                return True
    return False


def comment_audience(comment: dict | None) -> str:
    if not comment:
        return 'unknown'
    text = comment.get('text', '')
    if text.startswith('[EXTERNAL]'):
        return 'EXTERNAL'
    if text.startswith('[INTERNAL]'):
        return 'INTERNAL'
    return 'unknown'


def insert_comment_markers(document_xml_path: str, clause_map: dict,
                           comment_assignments: dict, output_path: str,
                           comments_by_id: dict | None = None) -> dict:
    """Insert comment range markers into document.xml."""
    w = NSMAP['w']

    tree = ET.parse(document_xml_path)
    root = tree.getroot()
    body = root.find(f'{{{w}}}body')

    if body is None:
        return {'error': 'No body in document.xml', 'success': False}

    all_paragraphs = list(body.iter(f'{{{w}}}p'))

    mapping_lookup = {}
    for mapping in clause_map.get('mappings', []):
        if mapping.get('mapped'):
            mapping_lookup[mapping['clause_id']] = mapping.get('paragraph_indices', [])

    applied = 0
    failures = []

    def record_failures(clause_id: str, comment_ids: list[int], reason: str, details: str | None = None) -> None:
        for comment_id in comment_ids:
            comment = (comments_by_id or {}).get(comment_id)
            failure = {
                'entry_id': str(comment_id),
                'clause_id': clause_id,
                'comment_id': comment_id,
                'audience': comment_audience(comment),
                'reason': reason,
            }
            if details:
                failure['details'] = details
            failures.append(failure)

    for clause_id, comment_ids in comment_assignments.items():
        para_indices = mapping_lookup.get(clause_id, [])
        if not para_indices:
            record_failures(clause_id, comment_ids, 'mapping_missing')
            continue

        para_idx = para_indices[0]
        if para_idx >= len(all_paragraphs):
            record_failures(
                clause_id,
                comment_ids,
                'paragraph_index_out_of_range',
                f'paragraph_index={para_idx}, paragraph_count={len(all_paragraphs)}',
            )
            continue

        para = all_paragraphs[para_idx]

        for comment_id in comment_ids:
            if paragraph_has_comment_reference(para, comment_id):
                continue

            start = ET.Element(f'{{{w}}}commentRangeStart')
            start.set(f'{{{w}}}id', str(comment_id))

            end = ET.Element(f'{{{w}}}commentRangeEnd')
            end.set(f'{{{w}}}id', str(comment_id))

            insert_at = first_direct_run_index(para)
            para.insert(insert_at, start)

            last_run_idx = last_direct_run_index(para)
            end_insert_at = last_run_idx + 1 if last_run_idx >= 0 else len(list(para))
            para.insert(end_insert_at, end)
            para.insert(end_insert_at + 1, make_comment_reference_run(comment_id))
            applied += 1

    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    return {
        'success': True,
        'output_path': output_path,
        'comments_applied': applied,
        'failed_count': len(failures),
        'failures': failures,
    }


def load_comment_reviewer_metadata(comments_data: dict) -> dict:
    """Resolve reviewer author/initials from JSON metadata or env vars."""
    meta = comments_data.get('_meta', {}) if isinstance(comments_data, dict) else {}
    reviewer = meta.get('reviewer', {}) if isinstance(meta, dict) else {}

    author = (
        reviewer.get('author')
        or meta.get('reviewer_author')
        or os.environ.get('DOCX_REVIEWER_AUTHOR')
        or DEFAULT_AUTHOR
    )
    initials = (
        reviewer.get('initials')
        or meta.get('reviewer_initials')
        or os.environ.get('DOCX_REVIEWER_INITIALS')
        or DEFAULT_INITIALS
    )

    return {'author': author, 'initials': initials}


def build_comment_payloads(comments_data: dict, comments_xml_path: str) -> tuple[list[dict], dict, dict, int]:
    """Build comment entries and per-clause assignments.

    Accepts both the v1 dict schema and the v2 list schema for each clause:

    v1 (legacy):
        {"clause-001": {"external_comment": "...", "internal_note": "..."}}

    v2 (AGENT.md Step 7, 2026-04-10 hardening):
        {"clause-001": [
            {"audience": "EXTERNAL", "text": "[EXTERNAL] ..."},
            {"audience": "INTERNAL", "text": "[INTERNAL] ..."}
        ]}

    Both schemas are fully supported to avoid silent comment drops during the
    migration window. The v2 schema is the canonical form going forward.

    Returns (all_comments, comment_assignments, reviewer, total_clause_comments).
    total_clause_comments counts how many comments the JSON *intended* to emit
    (before any schema skips), so callers can fail-loud when applied == 0 but
    the input had entries.
    """
    _, root = load_comments_root(comments_xml_path)
    next_id = next_comment_id(root)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    reviewer = load_comment_reviewer_metadata(comments_data)

    all_comments = []
    comment_assignments = {}
    total_clause_comments = 0

    def append_comment(clause_comment_ids: list, raw_text: str, prefix: str) -> None:
        nonlocal next_id
        if not raw_text:
            return
        # Ensure the audience prefix is present exactly once. If the caller
        # already wrote "[EXTERNAL] ..." into text, keep it. Otherwise prepend.
        if raw_text.startswith(prefix):
            text = raw_text
        else:
            text = f"{prefix} {raw_text}"
        all_comments.append({
            'id': next_id,
            'text': text,
            'author': reviewer['author'],
            'date': now,
            'initials': reviewer['initials'],
        })
        clause_comment_ids.append(next_id)
        next_id += 1

    for clause_id, clause_comments in comments_data.items():
        if clause_id == '_meta':
            continue

        clause_comment_ids: list[int] = []

        if isinstance(clause_comments, list):
            # v2 schema: array of {audience, text} objects
            for entry in clause_comments:
                if not isinstance(entry, dict):
                    continue
                total_clause_comments += 1
                audience = str(entry.get('audience', '')).upper()
                text = entry.get('text', '')
                if audience == 'EXTERNAL':
                    append_comment(clause_comment_ids, text, '[EXTERNAL]')
                elif audience == 'INTERNAL':
                    append_comment(clause_comment_ids, text, '[INTERNAL]')
                # Unknown audience → silently drop from output but still count
                # toward total_clause_comments so the fail-loud check fires.
        elif isinstance(clause_comments, dict):
            # v1 schema: single dict with external_comment / internal_note keys
            external_comment = clause_comments.get('external_comment')
            internal_note = clause_comments.get('internal_note')
            if external_comment:
                total_clause_comments += 1
                append_comment(clause_comment_ids, external_comment, '[EXTERNAL]')
            if internal_note:
                total_clause_comments += 1
                append_comment(clause_comment_ids, internal_note, '[INTERNAL]')
        # else: neither list nor dict → skip (malformed entry)

        if clause_comment_ids:
            comment_assignments[clause_id] = clause_comment_ids

    return all_comments, comment_assignments, reviewer, total_clause_comments


def apply_comments(unpacked_dir: str, clause_map_path: str,
                   comments_data_path: str) -> dict:
    """Full comment application workflow."""
    with open(clause_map_path, 'r', encoding='utf-8') as handle:
        clause_map = json.load(handle)

    with open(comments_data_path, 'r', encoding='utf-8') as handle:
        comments_data = json.load(handle)

    comments_xml_path = os.path.join(unpacked_dir, 'word', 'comments.xml')
    all_comments, comment_assignments, reviewer, total_clause_comments = build_comment_payloads(
        comments_data, comments_xml_path
    )

    # Fail-loud guard (2026-04-11 hardening): if the input JSON had comment
    # entries but zero were built (all skipped due to schema mismatch or
    # malformed entries), do not return success. The 2026-04-10 incident
    # included a "memos 0건" symptom alongside the redline 0건 symptom, and
    # apply-comments.py was previously the silent counterpart to
    # apply-redlines.py's silent success path. Matching apply-redlines.py
    # behavior: explicitly error out so Step 9 halts instead of producing a
    # DOCX with zero comments applied despite the LLM having written entries.
    if total_clause_comments > 0 and not all_comments:
        return {
            'success': False,
            'error': (
                f'No comments were built despite {total_clause_comments} comment '
                f'entries in the input. Likely causes: (1) unknown audience values '
                f'(must be "EXTERNAL" or "INTERNAL"), (2) missing text field, '
                f'(3) malformed entries (not dict or list). Check Step 7 output '
                f'schema in AGENT.md against docx-redliner/scripts/apply-comments.py.'
            ),
            'comments_applied': 0,
            'total_clause_comments': total_clause_comments,
            'total_entries': total_clause_comments,
            'applied_entries': 0,
            'failed_entries': total_clause_comments,
            'failed_critical_or_high': 0,
            'failure_rate': 1,
            'failures': [
                {
                    'entry_id': 'unknown',
                    'clause_id': 'unknown',
                    'audience': 'unknown',
                    'reason': 'no_comments_built',
                }
            ],
        }

    if not all_comments:
        # Legitimate "no comments to apply" case (e.g. loose review mode with
        # only Acceptable clauses). Distinct from the fail-loud case above.
        return {
            'success': True,
            'comments_applied': 0,
            'total_clause_comments': 0,
            'total_entries': 0,
            'applied_entries': 0,
            'failed_entries': 0,
            'failed_critical_or_high': 0,
            'failure_rate': 0,
            'failures': [],
            'message': 'No comments to apply',
        }

    comments_result = append_comments_xml(all_comments, comments_xml_path)
    relationship_added = ensure_comments_relationship(unpacked_dir)
    content_type_added = ensure_comments_content_type(unpacked_dir)

    doc_xml_path = os.path.join(unpacked_dir, 'word', 'document.xml')
    comments_by_id = {comment['id']: comment for comment in all_comments}
    result = insert_comment_markers(
        doc_xml_path,
        clause_map,
        comment_assignments,
        doc_xml_path,
        comments_by_id,
    )

    # Fail-loud guard part 2: even if we built comments, zero may have actually
    # landed in the DOCX if every clause failed to map via docx-clause-map.json.
    # This is the Step 8 mapping failure case.
    comments_applied_count = result.get('comments_applied', 0)
    failures = result.get('failures', [])
    failed_count = len(failures)
    failed_critical_or_high = len([
        failure for failure in failures if failure.get('audience') == 'EXTERNAL'
    ])
    failure_rate = (failed_count / len(all_comments)) if all_comments else 0
    if len(all_comments) > 0 and comments_applied_count == 0:
        result['success'] = False
        result['error'] = (
            f'{len(all_comments)} comments were built but zero were inserted '
            f'into the DOCX. Likely cause: Step 8 clause-to-DOCX mapping failed '
            f'for every clause that had a comment. Check docx-clause-map.json '
            f'coverage.'
        )
    elif failed_critical_or_high > 0:
        result['success'] = False
        result['error'] = (
            f'{failed_critical_or_high} EXTERNAL comment(s) failed to apply. '
            'Pipeline must halt so Critical/High review comments are not silently dropped.'
        )
    elif len(all_comments) > 0 and failure_rate > FAILURE_RATE_THRESHOLD:
        result['success'] = False
        result['error'] = (
            f'{failed_count} of {len(all_comments)} comments failed '
            f'({failure_rate:.0%}), exceeding the {FAILURE_RATE_THRESHOLD:.0%} threshold.'
        )

    result['total_comments'] = len(all_comments)
    result['total_clause_comments'] = total_clause_comments
    result['total_entries'] = len(all_comments)
    result['applied_entries'] = comments_applied_count
    result['failed_entries'] = failed_count
    result['failed_critical_or_high'] = failed_critical_or_high
    result['failure_rate'] = round(failure_rate, 3)
    result['comments_xml_updated'] = comments_result
    result['comments_relationship_added'] = relationship_added
    result['comments_content_type_added'] = content_type_added
    result['reviewer'] = reviewer
    return result


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            'error': 'Usage: apply-comments.py <unpacked_dir> <clause-map.json> <comments.json>'
        }))
        sys.exit(1)

    result = apply_comments(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()

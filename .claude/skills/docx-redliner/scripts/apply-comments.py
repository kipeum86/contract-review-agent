#!/usr/bin/env python3
"""
Apply comments to unpacked DOCX XML.
Creates comment entries in word/comments.xml and inserts
<w:commentRangeStart/End> markers in word/document.xml.
"""

import sys
import os
import json
import copy
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

for prefix, uri in NSMAP.items():
    ET.register_namespace(prefix, uri)
ET.register_namespace('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006')
ET.register_namespace('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing')

AUTHOR = 'Claude'
INITIALS = 'CL'


def create_comments_xml(comments: list[dict], output_path: str):
    """Create or update word/comments.xml with comment entries.

    Each comment dict has: id, text, author, date
    """
    w = NSMAP['w']

    root = ET.Element(f'{{{w}}}comments')

    for comment in comments:
        c_elem = ET.SubElement(root, f'{{{w}}}comment')
        c_elem.set(f'{{{w}}}id', str(comment['id']))
        c_elem.set(f'{{{w}}}author', comment.get('author', AUTHOR))
        c_elem.set(f'{{{w}}}date', comment.get('date', ''))
        c_elem.set(f'{{{w}}}initials', comment.get('initials', INITIALS))

        # Comment body as a paragraph
        p_elem = ET.SubElement(c_elem, f'{{{w}}}p')
        r_elem = ET.SubElement(p_elem, f'{{{w}}}r')
        t_elem = ET.SubElement(r_elem, f'{{{w}}}t')
        t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t_elem.text = comment['text']

    tree = ET.ElementTree(root)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)


def insert_comment_markers(document_xml_path: str, clause_map: dict,
                           comment_assignments: dict, output_path: str) -> dict:
    """Insert comment range markers into document.xml.

    Args:
        document_xml_path: path to word/document.xml
        clause_map: loaded docx-clause-map.json
        comment_assignments: dict mapping clause_id → list of comment IDs
        output_path: path to write modified document.xml

    Returns:
        dict with results
    """
    w = NSMAP['w']

    tree = ET.parse(document_xml_path)
    root = tree.getroot()
    body = root.find(f'{{{w}}}body')

    if body is None:
        return {'error': 'No body in document.xml', 'success': False}

    all_paragraphs = list(body.iter(f'{{{w}}}p'))

    # Build clause_id → paragraph indices
    mapping_lookup = {}
    for m in clause_map.get('mappings', []):
        if m.get('mapped'):
            mapping_lookup[m['clause_id']] = m.get('paragraph_indices', [])

    applied = 0
    for clause_id, comment_ids in comment_assignments.items():
        para_indices = mapping_lookup.get(clause_id, [])
        if not para_indices:
            continue

        para_idx = para_indices[0]
        if para_idx >= len(all_paragraphs):
            continue

        para = all_paragraphs[para_idx]

        for cid in comment_ids:
            # Insert commentRangeStart before the first run
            start = ET.Element(f'{{{w}}}commentRangeStart')
            start.set(f'{{{w}}}id', str(cid))

            end = ET.Element(f'{{{w}}}commentRangeEnd')
            end.set(f'{{{w}}}id', str(cid))

            # Comment reference run
            ref_run = ET.Element(f'{{{w}}}r')
            rPr = ET.SubElement(ref_run, f'{{{w}}}rPr')
            rStyle = ET.SubElement(rPr, f'{{{w}}}rStyle')
            rStyle.set(f'{{{w}}}val', 'CommentReference')
            comment_ref = ET.SubElement(ref_run, f'{{{w}}}commentReference')
            comment_ref.set(f'{{{w}}}id', str(cid))

            # Insert at beginning and end of paragraph
            para.insert(0, start)
            para.append(end)
            para.append(ref_run)

            applied += 1

    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    return {
        'success': True,
        'output_path': output_path,
        'comments_applied': applied,
    }


def apply_comments(unpacked_dir: str, clause_map_path: str,
                   comments_data_path: str) -> dict:
    """Full comment application workflow.

    Args:
        unpacked_dir: path to unpacked DOCX directory
        clause_map_path: path to docx-clause-map.json
        comments_data_path: path to JSON with comment data per clause

    Returns:
        dict with results
    """
    with open(clause_map_path, 'r', encoding='utf-8') as f:
        clause_map = json.load(f)

    with open(comments_data_path, 'r', encoding='utf-8') as f:
        comments_data = json.load(f)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Build comment list and assignments
    all_comments = []
    comment_assignments = {}
    comment_id = 1

    for clause_id, clause_comments in comments_data.items():
        clause_comment_ids = []

        # External comment
        ext = clause_comments.get('external_comment')
        if ext:
            all_comments.append({
                'id': comment_id,
                'text': f"[EXTERNAL] {ext}",
                'author': AUTHOR,
                'date': now,
                'initials': INITIALS,
            })
            clause_comment_ids.append(comment_id)
            comment_id += 1

        # Internal note
        internal = clause_comments.get('internal_note')
        if internal:
            all_comments.append({
                'id': comment_id,
                'text': f"[INTERNAL] {internal}",
                'author': AUTHOR,
                'date': now,
                'initials': INITIALS,
            })
            clause_comment_ids.append(comment_id)
            comment_id += 1

        if clause_comment_ids:
            comment_assignments[clause_id] = clause_comment_ids

    if not all_comments:
        return {'success': True, 'comments_applied': 0, 'message': 'No comments to apply'}

    # Create comments.xml
    comments_xml_path = os.path.join(unpacked_dir, 'word', 'comments.xml')
    create_comments_xml(all_comments, comments_xml_path)

    # Insert markers into document.xml
    doc_xml_path = os.path.join(unpacked_dir, 'word', 'document.xml')
    output_doc_path = doc_xml_path  # Overwrite in place

    result = insert_comment_markers(doc_xml_path, clause_map,
                                     comment_assignments, output_doc_path)

    result['total_comments'] = len(all_comments)
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

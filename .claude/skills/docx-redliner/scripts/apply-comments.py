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


def insert_comment_markers(document_xml_path: str, clause_map: dict,
                           comment_assignments: dict, output_path: str) -> dict:
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
    for clause_id, comment_ids in comment_assignments.items():
        para_indices = mapping_lookup.get(clause_id, [])
        if not para_indices:
            continue

        para_idx = para_indices[0]
        if para_idx >= len(all_paragraphs):
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


def build_comment_payloads(comments_data: dict, comments_xml_path: str) -> tuple[list[dict], dict, dict]:
    """Build comment entries and per-clause assignments."""
    _, root = load_comments_root(comments_xml_path)
    next_id = next_comment_id(root)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    reviewer = load_comment_reviewer_metadata(comments_data)

    all_comments = []
    comment_assignments = {}

    for clause_id, clause_comments in comments_data.items():
        if clause_id == '_meta' or not isinstance(clause_comments, dict):
            continue

        clause_comment_ids = []

        external_comment = clause_comments.get('external_comment')
        if external_comment:
            all_comments.append({
                'id': next_id,
                'text': f"[EXTERNAL] {external_comment}",
                'author': reviewer['author'],
                'date': now,
                'initials': reviewer['initials'],
            })
            clause_comment_ids.append(next_id)
            next_id += 1

        internal_note = clause_comments.get('internal_note')
        if internal_note:
            all_comments.append({
                'id': next_id,
                'text': f"[INTERNAL] {internal_note}",
                'author': reviewer['author'],
                'date': now,
                'initials': reviewer['initials'],
            })
            clause_comment_ids.append(next_id)
            next_id += 1

        if clause_comment_ids:
            comment_assignments[clause_id] = clause_comment_ids

    return all_comments, comment_assignments, reviewer


def apply_comments(unpacked_dir: str, clause_map_path: str,
                   comments_data_path: str) -> dict:
    """Full comment application workflow."""
    with open(clause_map_path, 'r', encoding='utf-8') as handle:
        clause_map = json.load(handle)

    with open(comments_data_path, 'r', encoding='utf-8') as handle:
        comments_data = json.load(handle)

    comments_xml_path = os.path.join(unpacked_dir, 'word', 'comments.xml')
    all_comments, comment_assignments, reviewer = build_comment_payloads(comments_data, comments_xml_path)

    if not all_comments:
        return {'success': True, 'comments_applied': 0, 'message': 'No comments to apply'}

    comments_result = append_comments_xml(all_comments, comments_xml_path)
    relationship_added = ensure_comments_relationship(unpacked_dir)
    content_type_added = ensure_comments_content_type(unpacked_dir)

    doc_xml_path = os.path.join(unpacked_dir, 'word', 'document.xml')
    result = insert_comment_markers(doc_xml_path, clause_map, comment_assignments, doc_xml_path)
    result['total_comments'] = len(all_comments)
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

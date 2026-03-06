#!/usr/bin/env python3
"""
Apply tracked changes (redlines) to unpacked DOCX XML.
Inserts <w:del> and <w:ins> elements with author="Claude".
Preserves original <w:rPr> formatting.

This script operates on the unpacked DOCX directory structure:
  unpacked/
    word/document.xml
    word/styles.xml
    [Content_Types].xml
    ...
"""

import sys
import os
import json
import re
import copy
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
}

# Register namespaces to preserve them during serialization
for prefix, uri in NSMAP.items():
    ET.register_namespace(prefix, uri)
# Additional namespaces commonly found in DOCX
ET.register_namespace('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006')
ET.register_namespace('o', 'urn:schemas-microsoft-com:office:office')
ET.register_namespace('m', 'http://schemas.openxmlformats.org/officeDocument/2006/math')
ET.register_namespace('v', 'urn:schemas-microsoft-com:vml')
ET.register_namespace('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing')
ET.register_namespace('a', 'http://schemas.openxmlformats.org/drawingml/2006/main')
ET.register_namespace('wps', 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape')

AUTHOR = 'Claude'


def make_revision_id() -> str:
    """Generate a unique revision ID."""
    import random
    return str(random.randint(1, 999999999))


def apply_redlines(document_xml_path: str, clause_map_path: str,
                   redlines_path: str, output_path: str) -> dict:
    """Apply tracked changes to document.xml.

    Args:
        document_xml_path: path to unpacked word/document.xml
        clause_map_path: path to docx-clause-map.json
        redlines_path: path to JSON file with redline suggestions per clause
        output_path: path to write modified document.xml

    Returns:
        dict with results
    """
    # Load inputs
    with open(clause_map_path, 'r', encoding='utf-8') as f:
        clause_map = json.load(f)

    with open(redlines_path, 'r', encoding='utf-8') as f:
        redlines = json.load(f)

    # Parse document XML
    tree = ET.parse(document_xml_path)
    root = tree.getroot()
    body = root.find(f'{{{NSMAP["w"]}}}body')

    if body is None:
        return {'error': 'No body element found in document.xml', 'success': False}

    # Build paragraph index
    all_paragraphs = list(body.iter(f'{{{NSMAP["w"]}}}p'))

    # Build clause_id → paragraph index mapping
    mapping_lookup = {}
    for m in clause_map.get('mappings', []):
        if m.get('mapped'):
            clause_id = m['clause_id']
            indices = m.get('paragraph_indices', [])
            mapping_lookup[clause_id] = indices

    applied_count = 0
    failed_count = 0
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    for clause_id, redline_data in redlines.items():
        suggested_text = redline_data.get('suggested_redline', '')
        if not suggested_text:
            continue

        para_indices = mapping_lookup.get(clause_id, [])
        if not para_indices:
            failed_count += 1
            continue

        # Apply redline to the first matched paragraph
        para_idx = para_indices[0]
        if para_idx >= len(all_paragraphs):
            failed_count += 1
            continue

        para = all_paragraphs[para_idx]

        try:
            _apply_tracked_change(para, suggested_text, now)
            applied_count += 1
        except Exception as e:
            failed_count += 1

    # Write modified XML
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    return {
        'success': True,
        'output_path': output_path,
        'applied_count': applied_count,
        'failed_count': failed_count,
        'total_redlines': len(redlines),
    }


def _apply_tracked_change(para_elem, new_text: str, date_str: str):
    """Apply a tracked change to a paragraph element.

    Strategy: wrap existing runs in <w:del>, add new text as <w:ins>.
    """
    w = NSMAP['w']
    rev_id = make_revision_id()

    # Collect existing runs and their formatting
    existing_runs = list(para_elem.findall(f'{{{w}}}r'))

    if not existing_runs:
        # No runs to delete — just insert
        ins_elem = ET.SubElement(para_elem, f'{{{w}}}ins')
        ins_elem.set(f'{{{w}}}id', rev_id)
        ins_elem.set(f'{{{w}}}author', AUTHOR)
        ins_elem.set(f'{{{w}}}date', date_str)
        new_run = ET.SubElement(ins_elem, f'{{{w}}}r')
        new_t = ET.SubElement(new_run, f'{{{w}}}t')
        new_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        new_t.text = new_text
        return

    # Get formatting from the first run
    first_run = existing_runs[0]
    rPr = first_run.find(f'{{{w}}}rPr')
    rPr_copy = copy.deepcopy(rPr) if rPr is not None else None

    # Wrap existing runs in <w:del>
    del_elem = ET.Element(f'{{{w}}}del')
    del_elem.set(f'{{{w}}}id', rev_id)
    del_elem.set(f'{{{w}}}author', AUTHOR)
    del_elem.set(f'{{{w}}}date', date_str)

    # Find position of first run in paragraph
    first_run_idx = list(para_elem).index(first_run)

    for run in existing_runs:
        # Create delText version
        del_run = copy.deepcopy(run)
        # Rename <w:t> to <w:delText>
        for t in del_run.findall(f'{{{w}}}t'):
            t.tag = f'{{{w}}}delText'
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        del_elem.append(del_run)
        para_elem.remove(run)

    # Insert <w:del> at the original position
    para_elem.insert(first_run_idx, del_elem)

    # Create <w:ins> with new text
    rev_id2 = make_revision_id()
    ins_elem = ET.Element(f'{{{w}}}ins')
    ins_elem.set(f'{{{w}}}id', rev_id2)
    ins_elem.set(f'{{{w}}}author', AUTHOR)
    ins_elem.set(f'{{{w}}}date', date_str)

    new_run = ET.SubElement(ins_elem, f'{{{w}}}r')
    if rPr_copy is not None:
        new_run.insert(0, rPr_copy)
    new_t = ET.SubElement(new_run, f'{{{w}}}t')
    new_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    new_t.text = new_text

    # Insert <w:ins> after <w:del>
    para_elem.insert(first_run_idx + 1, ins_elem)


def main():
    if len(sys.argv) < 5:
        print(json.dumps({
            'error': 'Usage: apply-redlines.py <document.xml> <clause-map.json> <redlines.json> <output.xml>'
        }))
        sys.exit(1)

    result = apply_redlines(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()

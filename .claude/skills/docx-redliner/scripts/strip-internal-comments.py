#!/usr/bin/env python3
"""
Strip [INTERNAL] comments from DOCX to produce external-clean version.
Safety-critical utility: prevents accidental internal strategy leakage.

Process:
1. Unpack DOCX (ZIP)
2. Parse word/comments.xml, identify [INTERNAL]-prefixed comments
3. Remove those comment entries from comments.xml
4. Remove corresponding commentRangeStart/End markers from document.xml
5. Repack DOCX
"""

import sys
import os
import json
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}

for prefix, uri in NSMAP.items():
    ET.register_namespace(prefix, uri)
ET.register_namespace('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006')
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')
ET.register_namespace('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing')
ET.register_namespace('a', 'http://schemas.openxmlformats.org/drawingml/2006/main')
ET.register_namespace('wps', 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape')
ET.register_namespace('w14', 'http://schemas.microsoft.com/office/word/2010/wordml')


def unpack_docx(docx_path: str, output_dir: str):
    """Unpack a DOCX file into a directory."""
    with zipfile.ZipFile(docx_path, 'r') as z:
        z.extractall(output_dir)


def pack_docx(source_dir: str, output_path: str):
    """Repack a directory into a DOCX file."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(source_dir):
            for fn in files:
                file_path = os.path.join(root, fn)
                arcname = os.path.relpath(file_path, source_dir)
                z.write(file_path, arcname)


def strip_internal_comments(input_docx: str, output_docx: str) -> dict:
    """Strip all [INTERNAL]-prefixed comments from a DOCX file.

    Args:
        input_docx: path to internal version DOCX
        output_docx: path to write external-clean DOCX

    Returns:
        dict with results
    """
    w = NSMAP['w']

    # Create temp directory for unpacking
    temp_dir = output_docx + '_temp'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    try:
        # Unpack
        unpack_docx(input_docx, temp_dir)

        # Find and process comments.xml
        comments_xml_path = os.path.join(temp_dir, 'word', 'comments.xml')
        internal_ids = set()

        if os.path.exists(comments_xml_path):
            tree = ET.parse(comments_xml_path)
            root = tree.getroot()

            # Find [INTERNAL] comments
            comments_to_remove = []
            for comment in root.findall(f'{{{w}}}comment'):
                comment_id = comment.get(f'{{{w}}}id')
                # Check comment text
                text_parts = []
                for t in comment.iter(f'{{{w}}}t'):
                    if t.text:
                        text_parts.append(t.text)
                full_text = ''.join(text_parts)

                if full_text.strip().startswith('[INTERNAL]'):
                    internal_ids.add(comment_id)
                    comments_to_remove.append(comment)

            # Remove [INTERNAL] comments
            for comment in comments_to_remove:
                root.remove(comment)

            tree.write(comments_xml_path, encoding='UTF-8', xml_declaration=True)

        # Remove markers from document.xml
        doc_xml_path = os.path.join(temp_dir, 'word', 'document.xml')
        removed_markers = 0

        if internal_ids and os.path.exists(doc_xml_path):
            doc_tree = ET.parse(doc_xml_path)
            doc_root = doc_tree.getroot()

            # Remove commentRangeStart, commentRangeEnd, and commentReference
            # for internal comment IDs
            for parent in doc_root.iter():
                children_to_remove = []
                for child in parent:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if tag in ('commentRangeStart', 'commentRangeEnd'):
                        cid = child.get(f'{{{w}}}id')
                        if cid in internal_ids:
                            children_to_remove.append(child)
                    elif tag == 'r':
                        # Check for commentReference
                        for sub in child:
                            sub_tag = sub.tag.split('}')[-1] if '}' in sub.tag else sub.tag
                            if sub_tag == 'commentReference':
                                cid = sub.get(f'{{{w}}}id')
                                if cid in internal_ids:
                                    children_to_remove.append(child)
                                    break

                for child in children_to_remove:
                    parent.remove(child)
                    removed_markers += 1

            doc_tree.write(doc_xml_path, encoding='UTF-8', xml_declaration=True)

        # Repack
        os.makedirs(os.path.dirname(output_docx), exist_ok=True)
        pack_docx(temp_dir, output_docx)

        return {
            'success': True,
            'input_docx': input_docx,
            'output_docx': output_docx,
            'internal_comments_stripped': len(internal_ids),
            'markers_removed': removed_markers,
        }

    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            'error': 'Usage: strip-internal-comments.py <input.docx> <output.docx>'
        }))
        sys.exit(1)

    result = strip_internal_comments(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()

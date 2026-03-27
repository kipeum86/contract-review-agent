#!/usr/bin/env python3
"""
Strip [INTERNAL] comments from DOCX to produce external-clean version.
Safety-critical utility: prevents accidental internal strategy leakage.

This scrubber removes internal comments from:
- `word/comments.xml`
- comment anchors in document/body/header/footer/endnote/footnote parts
- related OOXML metadata parts such as threaded comments and comment IDs
- stale relationships and content-type overrides for deleted comment parts
"""

import sys
import os
import json
import shutil
import zipfile
import posixpath
import glob
import xml.etree.ElementTree as ET

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
    'w16cid': 'http://schemas.microsoft.com/office/word/2016/wordml/cid',
}
REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'

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
    with zipfile.ZipFile(docx_path, 'r') as archive:
        archive.extractall(output_dir)


def pack_docx(source_dir: str, output_path: str):
    """Repack a directory into a DOCX file."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for root, _, files in os.walk(source_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                arcname = os.path.relpath(file_path, source_dir)
                archive.write(file_path, arcname)


def local_name(tag: str) -> str:
    """Return the local XML tag name without namespace."""
    return tag.split('}')[-1] if '}' in tag else tag


def get_attr_local(element: ET.Element, attr_name: str) -> str | None:
    """Read an attribute by local name regardless of namespace prefix."""
    for key, value in element.attrib.items():
        if key == attr_name or key.endswith(f'}}{attr_name}'):
            return value
    return None


def extract_text(element: ET.Element) -> str:
    """Concatenate all text nodes within an element."""
    text_parts = []
    for node in element.iter():
        if local_name(node.tag) == 't' and node.text:
            text_parts.append(node.text)
    return ''.join(text_parts)


def normalize_archive_path(path: str) -> str:
    """Normalize a DOCX internal path to forward-slash form."""
    normalized = path.replace('\\', '/').lstrip('/')
    normalized = posixpath.normpath(normalized)
    return '' if normalized == '.' else normalized


def load_xml(path: str) -> tuple[ET.ElementTree | None, ET.Element | None]:
    """Load an XML file if it exists."""
    if not os.path.exists(path):
        return None, None
    tree = ET.parse(path)
    return tree, tree.getroot()


def story_part_paths(word_dir: str) -> list[str]:
    """Return XML story parts that can contain comment anchors."""
    paths = []
    for filename in ('document.xml', 'footnotes.xml', 'endnotes.xml'):
        candidate = os.path.join(word_dir, filename)
        if os.path.exists(candidate):
            paths.append(candidate)

    for pattern in ('header*.xml', 'footer*.xml'):
        paths.extend(sorted(glob.glob(os.path.join(word_dir, pattern))))

    return paths


def run_contains_internal_reference(run_element: ET.Element, internal_ids: set[str]) -> bool:
    """Return True if a run only serves as an internal comment reference anchor."""
    for child in run_element:
        if local_name(child.tag) == 'commentReference':
            comment_id = get_attr_local(child, 'id')
            if comment_id in internal_ids:
                return True
    return False


def prune_comment_markers(parent: ET.Element, internal_ids: set[str]) -> tuple[int, int]:
    """Remove comment range markers and comment-reference runs recursively."""
    removed_markers = 0
    removed_reference_runs = 0

    for child in list(parent):
        tag = local_name(child.tag)

        if tag in ('commentRangeStart', 'commentRangeEnd'):
            comment_id = get_attr_local(child, 'id')
            if comment_id in internal_ids:
                parent.remove(child)
                removed_markers += 1
                continue

        if tag == 'r' and run_contains_internal_reference(child, internal_ids):
            parent.remove(child)
            removed_reference_runs += 1
            continue

        if tag == 'commentReference':
            comment_id = get_attr_local(child, 'id')
            if comment_id in internal_ids:
                parent.remove(child)
                removed_reference_runs += 1
                continue

        child_markers, child_reference_runs = prune_comment_markers(child, internal_ids)
        removed_markers += child_markers
        removed_reference_runs += child_reference_runs

    return removed_markers, removed_reference_runs


def remove_comment_markers_from_story_parts(word_dir: str, internal_ids: set[str]) -> dict:
    """Remove comment anchors from body/header/footer story parts."""
    results = {
        'story_parts_scanned': 0,
        'story_parts_changed': 0,
        'markers_removed': 0,
        'reference_runs_removed': 0,
    }

    if not internal_ids:
        return results

    for part_path in story_part_paths(word_dir):
        tree, root = load_xml(part_path)
        if tree is None or root is None:
            continue

        results['story_parts_scanned'] += 1
        removed_markers, removed_reference_runs = prune_comment_markers(root, internal_ids)
        if removed_markers or removed_reference_runs:
            tree.write(part_path, encoding='UTF-8', xml_declaration=True)
            results['story_parts_changed'] += 1
            results['markers_removed'] += removed_markers
            results['reference_runs_removed'] += removed_reference_runs

    return results


def parse_comments_extended_entries(part_path: str) -> tuple[ET.ElementTree | None, ET.Element | None, list[dict]]:
    """Load commentsExtended.xml entries."""
    tree, root = load_xml(part_path)
    if tree is None or root is None:
        return None, None, []

    entries = []
    for element in list(root):
        entries.append({
            'element': element,
            'para_id': get_attr_local(element, 'paraId'),
            'parent_para_id': get_attr_local(element, 'paraIdParent'),
        })
    return tree, root, entries


def parse_threaded_comment_entries(part_path: str) -> tuple[ET.ElementTree | None, ET.Element | None, list[dict]]:
    """Load threadedComments.xml entries."""
    tree, root = load_xml(part_path)
    if tree is None or root is None:
        return None, None, []

    entries = []
    for element in list(root):
        entries.append({
            'element': element,
            'thread_id': get_attr_local(element, 'id'),
            'parent_id': get_attr_local(element, 'parentId'),
            'para_id': get_attr_local(element, 'paraId'),
            'is_internal': extract_text(element).strip().startswith('[INTERNAL]'),
        })
    return tree, root, entries


def expand_internal_comment_closure(
    internal_para_ids: set[str],
    comments_extended_entries: list[dict],
    threaded_entries: list[dict],
) -> tuple[set[str], set[str]]:
    """Expand the set of internal para IDs to include descendants and replies."""
    expanded_para_ids = {para_id for para_id in internal_para_ids if para_id}
    internal_thread_ids = set()

    changed = True
    while changed:
        changed = False

        for entry in comments_extended_entries:
            para_id = entry.get('para_id')
            parent_para_id = entry.get('parent_para_id')
            if para_id and para_id in expanded_para_ids:
                continue
            if para_id and parent_para_id and parent_para_id in expanded_para_ids:
                expanded_para_ids.add(para_id)
                changed = True

        for entry in threaded_entries:
            thread_id = entry.get('thread_id')
            parent_id = entry.get('parent_id')
            para_id = entry.get('para_id')
            should_remove = (
                entry.get('is_internal')
                or (para_id and para_id in expanded_para_ids)
                or (parent_id and parent_id in internal_thread_ids)
            )
            if not should_remove:
                continue

            if thread_id and thread_id not in internal_thread_ids:
                internal_thread_ids.add(thread_id)
                changed = True
            if para_id and para_id not in expanded_para_ids:
                expanded_para_ids.add(para_id)
                changed = True

    return expanded_para_ids, internal_thread_ids


def remove_xml_entries(
    part_path: str,
    tree: ET.ElementTree | None,
    root: ET.Element | None,
    entries: list[dict],
    should_remove,
) -> dict:
    """Remove selected entries from an XML part and optionally delete the part."""
    result = {
        'removed_entries': 0,
        'deleted_part': False,
    }

    if tree is None or root is None:
        return result

    removed_entries = 0
    for entry in entries:
        if should_remove(entry):
            root.remove(entry['element'])
            removed_entries += 1

    if not removed_entries:
        return result

    result['removed_entries'] = removed_entries
    if len(list(root)) == 0:
        os.remove(part_path)
        result['deleted_part'] = True
        return result

    tree.write(part_path, encoding='UTF-8', xml_declaration=True)
    return result


def collect_internal_comments(comments_xml_path: str) -> dict:
    """Remove [INTERNAL] comments from comments.xml and collect IDs."""
    result = {
        'internal_ids': set(),
        'internal_para_ids': set(),
        'internal_comments_stripped': 0,
        'comments_part_deleted': False,
    }

    tree, root = load_xml(comments_xml_path)
    if tree is None or root is None:
        return result

    comments_to_remove = []
    for comment in root.findall(f'{{{NSMAP["w"]}}}comment'):
        comment_id = get_attr_local(comment, 'id')
        comment_text = extract_text(comment)
        if not comment_text.strip().startswith('[INTERNAL]'):
            continue

        para_id = get_attr_local(comment, 'paraId')
        if comment_id is not None:
            result['internal_ids'].add(str(comment_id))
        if para_id:
            result['internal_para_ids'].add(para_id)
        comments_to_remove.append(comment)

    for comment in comments_to_remove:
        root.remove(comment)

    result['internal_comments_stripped'] = len(comments_to_remove)

    if not comments_to_remove:
        return result

    if len(root.findall(f'{{{NSMAP["w"]}}}comment')) == 0:
        os.remove(comments_xml_path)
        result['comments_part_deleted'] = True
        return result

    tree.write(comments_xml_path, encoding='UTF-8', xml_declaration=True)
    return result


def relationship_base_dir(source_dir: str, rels_path: str) -> str:
    """Resolve the base directory used for Targets in a .rels file."""
    relative_path = normalize_archive_path(os.path.relpath(rels_path, source_dir))
    rels_dir = posixpath.dirname(relative_path)
    if rels_dir.endswith('/_rels'):
        return rels_dir[:-len('/_rels')]
    if rels_dir == '_rels':
        return ''
    return rels_dir


def resolve_relationship_target(base_dir: str, target: str) -> str:
    """Resolve a relationship target to a normalized DOCX part path."""
    normalized_target = target.replace('\\', '/')
    if normalized_target.startswith('/'):
        return normalize_archive_path(normalized_target)
    return normalize_archive_path(posixpath.join(base_dir, normalized_target))


def remove_relationships_for_deleted_parts(source_dir: str, deleted_parts: set[str]) -> int:
    """Remove stale relationship entries that point to deleted comment parts."""
    removed_relationships = 0
    if not deleted_parts:
        return removed_relationships

    for rels_path in glob.glob(os.path.join(source_dir, '**', '*.rels'), recursive=True):
        tree, root = load_xml(rels_path)
        if tree is None or root is None:
            continue

        base_dir = relationship_base_dir(source_dir, rels_path)
        removed_here = 0
        for relationship in list(root):
            target = relationship.get('Target')
            if not target:
                continue
            resolved_target = resolve_relationship_target(base_dir, target)
            if resolved_target in deleted_parts:
                root.remove(relationship)
                removed_here += 1

        if removed_here:
            tree.write(rels_path, encoding='UTF-8', xml_declaration=True)
            removed_relationships += removed_here

    return removed_relationships


def remove_content_types_for_deleted_parts(source_dir: str, deleted_parts: set[str]) -> int:
    """Remove stale content-type overrides for deleted comment parts."""
    if not deleted_parts:
        return 0

    content_types_path = os.path.join(source_dir, '[Content_Types].xml')
    tree, root = load_xml(content_types_path)
    if tree is None or root is None:
        return 0

    removed_overrides = 0
    for override in list(root):
        part_name = override.get('PartName')
        if not part_name:
            continue
        if normalize_archive_path(part_name) in deleted_parts:
            root.remove(override)
            removed_overrides += 1

    if removed_overrides:
        tree.write(content_types_path, encoding='UTF-8', xml_declaration=True)

    return removed_overrides


def strip_internal_comments(input_docx: str, output_docx: str) -> dict:
    """Strip all [INTERNAL]-prefixed comments from a DOCX file."""
    temp_dir = output_docx + '_temp'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    try:
        unpack_docx(input_docx, temp_dir)

        word_dir = os.path.join(temp_dir, 'word')
        comments_xml_path = os.path.join(word_dir, 'comments.xml')
        comments_extended_path = os.path.join(word_dir, 'commentsExtended.xml')
        comments_ids_path = os.path.join(word_dir, 'commentsIds.xml')
        threaded_comments_path = os.path.join(word_dir, 'threadedComments.xml')
        people_xml_path = os.path.join(word_dir, 'people.xml')

        internal_state = collect_internal_comments(comments_xml_path)
        internal_ids = internal_state['internal_ids']

        marker_results = remove_comment_markers_from_story_parts(word_dir, internal_ids)

        comments_extended_tree, comments_extended_root, comments_extended_entries = (
            parse_comments_extended_entries(comments_extended_path)
        )
        threaded_tree, threaded_root, threaded_entries = (
            parse_threaded_comment_entries(threaded_comments_path)
        )

        internal_para_ids, internal_thread_ids = expand_internal_comment_closure(
            internal_state['internal_para_ids'],
            comments_extended_entries,
            threaded_entries,
        )

        comments_extended_result = remove_xml_entries(
            comments_extended_path,
            comments_extended_tree,
            comments_extended_root,
            comments_extended_entries,
            lambda entry: entry.get('para_id') in internal_para_ids,
        )

        threaded_result = remove_xml_entries(
            threaded_comments_path,
            threaded_tree,
            threaded_root,
            threaded_entries,
            lambda entry: (
                entry.get('thread_id') in internal_thread_ids
                or entry.get('para_id') in internal_para_ids
            ),
        )

        comments_ids_tree, comments_ids_root = load_xml(comments_ids_path)
        comments_ids_entries = []
        if comments_ids_tree is not None and comments_ids_root is not None:
            for element in list(comments_ids_root):
                comments_ids_entries.append({
                    'element': element,
                    'para_id': get_attr_local(element, 'paraId'),
                })

        comments_ids_result = remove_xml_entries(
            comments_ids_path,
            comments_ids_tree,
            comments_ids_root,
            comments_ids_entries,
            lambda entry: entry.get('para_id') in internal_para_ids,
        )

        deleted_parts = set()
        if internal_state['comments_part_deleted']:
            deleted_parts.add('word/comments.xml')
        if comments_extended_result['deleted_part']:
            deleted_parts.add('word/commentsExtended.xml')
        if threaded_result['deleted_part']:
            deleted_parts.add('word/threadedComments.xml')
        if comments_ids_result['deleted_part']:
            deleted_parts.add('word/commentsIds.xml')

        if threaded_result['deleted_part'] and os.path.exists(people_xml_path):
            os.remove(people_xml_path)
            deleted_parts.add('word/people.xml')

        removed_relationships = remove_relationships_for_deleted_parts(temp_dir, deleted_parts)
        removed_content_types = remove_content_types_for_deleted_parts(temp_dir, deleted_parts)

        output_dir = os.path.dirname(output_docx)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        pack_docx(temp_dir, output_docx)

        return {
            'success': True,
            'input_docx': input_docx,
            'output_docx': output_docx,
            'internal_comments_stripped': internal_state['internal_comments_stripped'],
            'internal_threaded_comments_stripped': threaded_result['removed_entries'],
            'internal_para_ids_removed': len(internal_para_ids),
            'markers_removed': marker_results['markers_removed'],
            'reference_runs_removed': marker_results['reference_runs_removed'],
            'story_parts_scanned': marker_results['story_parts_scanned'],
            'story_parts_changed': marker_results['story_parts_changed'],
            'deleted_parts': sorted(deleted_parts),
            'deleted_part_count': len(deleted_parts),
            'relationships_removed': removed_relationships,
            'content_types_removed': removed_content_types,
            'comments_extended_entries_removed': comments_extended_result['removed_entries'],
            'comments_ids_removed': comments_ids_result['removed_entries'],
        }

    finally:
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

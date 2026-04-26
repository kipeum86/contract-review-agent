#!/usr/bin/env python3
"""
Apply tracked changes (redlines) to unpacked DOCX XML.

This implementation preserves unrelated OOXML structure, accepts reviewer
metadata from redline JSON or environment variables, and performs partial
tracked changes by preserving common prefix/suffix text where possible.
"""

import sys
import os
import json
import copy
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
}

for prefix, uri in NSMAP.items():
    ET.register_namespace(prefix, uri)
ET.register_namespace('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006')
ET.register_namespace('o', 'urn:schemas-microsoft-com:office:office')
ET.register_namespace('m', 'http://schemas.openxmlformats.org/officeDocument/2006/math')
ET.register_namespace('v', 'urn:schemas-microsoft-com:vml')
ET.register_namespace('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing')
ET.register_namespace('a', 'http://schemas.openxmlformats.org/drawingml/2006/main')
ET.register_namespace('wps', 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape')

DEFAULT_AUTHOR = 'Reviewer'
DEFAULT_INITIALS = 'RV'
FAILURE_RATE_THRESHOLD = 0.10


def local_name(tag: str) -> str:
    """Return the local name of an XML tag."""
    return tag.split('}')[-1] if '}' in tag else tag


def get_attr_local(element: ET.Element, attr_name: str) -> str | None:
    """Read an attribute by local name regardless of namespace."""
    for key, value in element.attrib.items():
        if key == attr_name or key.endswith(f'}}{attr_name}'):
            return value
    return None


def make_revision_id(root: ET.Element) -> int:
    """Return the next available tracked-change ID in the document."""
    max_id = 0
    for element in root.iter():
        if local_name(element.tag) not in ('ins', 'del'):
            continue
        rev_id = get_attr_local(element, 'id')
        if rev_id is None:
            continue
        try:
            max_id = max(max_id, int(rev_id))
        except ValueError:
            continue
    return max_id + 1


def load_reviewer_metadata(redlines: dict) -> dict:
    """Resolve reviewer metadata from JSON or environment variables."""
    meta = redlines.get('_meta', {}) if isinstance(redlines, dict) else {}
    reviewer = meta.get('reviewer', {}) if isinstance(meta, dict) else {}

    return {
        'author': (
            reviewer.get('author')
            or meta.get('reviewer_author')
            or os.environ.get('DOCX_REVIEWER_AUTHOR')
            or DEFAULT_AUTHOR
        ),
        'initials': (
            reviewer.get('initials')
            or meta.get('reviewer_initials')
            or os.environ.get('DOCX_REVIEWER_INITIALS')
            or DEFAULT_INITIALS
        ),
    }


def normalize_risk_level(value) -> str:
    if value is None:
        return ''
    return str(value).strip().lower()


def is_critical_or_high(risk_level: str) -> bool:
    return normalize_risk_level(risk_level) in {'critical', 'high'}


def paragraph_text(paragraph: ET.Element) -> str:
    """Extract plain text from direct runs in a paragraph."""
    parts = []
    for child in paragraph:
        if local_name(child.tag) != 'r':
            continue
        parts.append(run_text(child))
    return ''.join(parts)


def run_text(run: ET.Element) -> str:
    """Extract text-like content from a run."""
    parts = []
    for child in run:
        child_name = local_name(child.tag)
        if child_name in ('t', 'delText'):
            parts.append(child.text or '')
        elif child_name == 'tab':
            parts.append('\t')
        elif child_name in ('br', 'cr'):
            parts.append('\n')
    return ''.join(parts)


def first_run_index(paragraph: ET.Element) -> int:
    """Return the first direct run index in a paragraph."""
    for index, child in enumerate(list(paragraph)):
        if local_name(child.tag) == 'r':
            return index
    return len(list(paragraph))


def direct_runs(paragraph: ET.Element) -> list[ET.Element]:
    """Return direct run children."""
    return [child for child in list(paragraph) if local_name(child.tag) == 'r']


def first_run_properties_copy(paragraph: ET.Element) -> ET.Element | None:
    """Copy the first run properties block for reuse."""
    for run in direct_runs(paragraph):
        run_props = run.find(f'{{{NSMAP["w"]}}}rPr')
        if run_props is not None:
            return copy.deepcopy(run_props)
    return None


def split_redline_paragraphs(text: str) -> list[str]:
    """Split suggested redline text into paragraph-sized chunks."""
    if text is None:
        return []

    parts = [part.strip('\r') for part in re.split(r'\n{2,}|\r\n\r\n', text)]
    parts = [part for part in parts if part != '']
    return parts if parts else [text]


def common_prefix_length(left: str, right: str) -> int:
    """Return the longest common prefix length."""
    max_len = min(len(left), len(right))
    index = 0
    while index < max_len and left[index] == right[index]:
        index += 1
    return index


def common_suffix_length(left: str, right: str, prefix_length: int) -> int:
    """Return the longest common suffix length after excluding the prefix."""
    max_suffix = min(len(left), len(right)) - prefix_length
    suffix = 0
    while (
        suffix < max_suffix
        and left[len(left) - suffix - 1] == right[len(right) - suffix - 1]
    ):
        suffix += 1
    return suffix


def is_token_char(value: str) -> bool:
    """Return True when a character looks like part of the same token."""
    return value.isalnum() or value == '_'


def adjust_diff_boundaries(left: str, right: str, prefix_len: int, suffix_len: int) -> tuple[int, int]:
    """Avoid splitting tracked changes in the middle of a token when possible."""
    if suffix_len <= 0:
        return prefix_len, suffix_len

    while True:
        left_suffix_start = len(left) - suffix_len
        right_suffix_start = len(right) - suffix_len
        if left_suffix_start <= prefix_len or right_suffix_start <= prefix_len:
            break

        left_prev = left[left_suffix_start - 1]
        left_curr = left[left_suffix_start]
        right_prev = right[right_suffix_start - 1]
        right_curr = right[right_suffix_start]

        if not (
            is_token_char(left_prev)
            and is_token_char(left_curr)
            and is_token_char(right_prev)
            and is_token_char(right_curr)
        ):
            break

        suffix_len -= 1
        if suffix_len <= 0:
            break

    return prefix_len, suffix_len


def make_plain_run(text: str, run_props: ET.Element | None) -> ET.Element:
    """Create a plain run."""
    w = NSMAP['w']
    run = ET.Element(f'{{{w}}}r')
    if run_props is not None:
        run.append(copy.deepcopy(run_props))
    text_elem = ET.SubElement(run, f'{{{w}}}t')
    text_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    text_elem.text = text
    return run


def make_insertion(text: str, run_props: ET.Element | None, revision_id: int, reviewer: dict, date_str: str) -> ET.Element:
    """Create a w:ins element."""
    w = NSMAP['w']
    ins_elem = ET.Element(f'{{{w}}}ins')
    ins_elem.set(f'{{{w}}}id', str(revision_id))
    ins_elem.set(f'{{{w}}}author', reviewer['author'])
    ins_elem.set(f'{{{w}}}date', date_str)

    run = ET.SubElement(ins_elem, f'{{{w}}}r')
    if run_props is not None:
        run.insert(0, copy.deepcopy(run_props))
    text_elem = ET.SubElement(run, f'{{{w}}}t')
    text_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    text_elem.text = text
    return ins_elem


def make_deletion(text: str, paragraph: ET.Element, revision_id: int, reviewer: dict, date_str: str) -> ET.Element:
    """Create a w:del element from current paragraph formatting."""
    w = NSMAP['w']
    del_elem = ET.Element(f'{{{w}}}del')
    del_elem.set(f'{{{w}}}id', str(revision_id))
    del_elem.set(f'{{{w}}}author', reviewer['author'])
    del_elem.set(f'{{{w}}}date', date_str)

    runs = direct_runs(paragraph)
    if not runs:
        del_run = ET.SubElement(del_elem, f'{{{w}}}r')
        del_text = ET.SubElement(del_run, f'{{{w}}}delText')
        del_text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        del_text.text = text
        return del_elem

    first_run_props = first_run_properties_copy(paragraph)
    del_run = ET.SubElement(del_elem, f'{{{w}}}r')
    if first_run_props is not None:
        del_run.insert(0, copy.deepcopy(first_run_props))
    del_text = ET.SubElement(del_run, f'{{{w}}}delText')
    del_text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    del_text.text = text
    return del_elem


def replace_runs_with_partial_redline(paragraph: ET.Element, new_text: str, reviewer: dict,
                                      date_str: str, next_revision_id: list[int]) -> bool:
    """Apply a partial tracked change while preserving common prefix/suffix."""
    current_text = paragraph_text(paragraph)
    if current_text == new_text:
        return False

    prefix_len = common_prefix_length(current_text, new_text)
    suffix_len = common_suffix_length(current_text, new_text, prefix_len)
    prefix_len, suffix_len = adjust_diff_boundaries(current_text, new_text, prefix_len, suffix_len)

    old_middle_end = len(current_text) - suffix_len if suffix_len else len(current_text)
    new_middle_end = len(new_text) - suffix_len if suffix_len else len(new_text)

    prefix_text = current_text[:prefix_len]
    old_middle = current_text[prefix_len:old_middle_end]
    new_middle = new_text[prefix_len:new_middle_end]
    suffix_text = current_text[old_middle_end:]

    run_props = first_run_properties_copy(paragraph)
    runs = direct_runs(paragraph)
    insert_at = first_run_index(paragraph)

    for run in runs:
        paragraph.remove(run)

    new_children = []
    if prefix_text:
        new_children.append(make_plain_run(prefix_text, run_props))
    if old_middle:
        new_children.append(make_deletion(old_middle, paragraph, next_revision_id[0], reviewer, date_str))
        next_revision_id[0] += 1
    if new_middle:
        new_children.append(make_insertion(new_middle, run_props, next_revision_id[0], reviewer, date_str))
        next_revision_id[0] += 1
    if suffix_text:
        new_children.append(make_plain_run(suffix_text, run_props))

    if not new_children:
        new_children.append(make_plain_run(new_text, run_props))

    for offset, child in enumerate(new_children):
        paragraph.insert(insert_at + offset, child)

    return True


def apply_redlines(document_xml_path: str, clause_map_path: str,
                   redlines_path: str, output_path: str) -> dict:
    """Apply tracked changes to document.xml."""
    with open(clause_map_path, 'r', encoding='utf-8') as handle:
        clause_map = json.load(handle)

    with open(redlines_path, 'r', encoding='utf-8') as handle:
        redlines = json.load(handle)

    tree = ET.parse(document_xml_path)
    root = tree.getroot()
    body = root.find(f'{{{NSMAP["w"]}}}body')

    if body is None:
        return {'error': 'No body element found in document.xml', 'success': False}

    all_paragraphs = list(body.iter(f'{{{NSMAP["w"]}}}p'))

    mapping_lookup = {}
    for mapping in clause_map.get('mappings', []):
        if mapping.get('mapped'):
            mapping_lookup[mapping['clause_id']] = mapping

    applied_count = 0
    failures = []
    paragraphs_touched = 0
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    reviewer = load_reviewer_metadata(redlines)
    next_revision_id = [make_revision_id(root)]

    def record_failure(clause_id: str, redline_data: dict, reason: str, details: str | None = None) -> None:
        mapping = mapping_lookup.get(clause_id, {})
        risk_level = (
            redline_data.get('risk_level')
            or redline_data.get('risk')
            or mapping.get('risk_level')
            or mapping.get('risk')
            or 'unknown'
        )
        failure = {
            'entry_id': clause_id,
            'clause_id': clause_id,
            'risk': risk_level,
            'reason': reason,
        }
        if details:
            failure['details'] = details
        failures.append(failure)

    for clause_id, redline_data in redlines.items():
        if clause_id == '_meta':
            continue

        if not isinstance(redline_data, dict):
            record_failure(clause_id, {}, 'malformed_entry')
            continue

        suggested_text = redline_data.get('suggested_redline', '')
        if not suggested_text:
            record_failure(clause_id, redline_data, 'missing_suggested_redline')
            continue

        mapping = mapping_lookup.get(clause_id, {})
        para_indices = mapping.get('paragraph_indices', [])
        if not para_indices:
            record_failure(clause_id, redline_data, 'mapping_missing')
            continue

        confidence = mapping.get('confidence')
        if isinstance(confidence, (int, float)) and confidence < 0.85:
            record_failure(
                clause_id,
                redline_data,
                'mapping_low_confidence',
                f'confidence={confidence}',
            )
            continue

        target_paragraphs = split_redline_paragraphs(suggested_text)
        if len(target_paragraphs) == 1 and len(para_indices) > 1:
            record_failure(
                clause_id,
                redline_data,
                'paragraph_count_mismatch',
                f'suggested paragraphs=1, mapped paragraphs={len(para_indices)}',
            )
            continue
        elif len(target_paragraphs) != len(para_indices):
            record_failure(
                clause_id,
                redline_data,
                'paragraph_count_mismatch',
                f'suggested paragraphs={len(target_paragraphs)}, mapped paragraphs={len(para_indices)}',
            )
            continue

        clause_applied = False
        try:
            for para_idx, paragraph_text_target in zip(para_indices, target_paragraphs):
                if para_idx >= len(all_paragraphs):
                    continue
                changed = replace_runs_with_partial_redline(
                    all_paragraphs[para_idx],
                    paragraph_text_target,
                    reviewer,
                    now,
                    next_revision_id,
                )
                if changed:
                    paragraphs_touched += 1
                    clause_applied = True

            if clause_applied:
                applied_count += 1
            else:
                record_failure(clause_id, redline_data, 'no_change_detected')
        except Exception as exc:
            record_failure(clause_id, redline_data, 'exception', str(exc))

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    total_redlines = len([key for key in redlines.keys() if key != '_meta'])
    failed_count = len(failures)
    failed_critical_or_high = len([
        failure for failure in failures if is_critical_or_high(failure.get('risk', ''))
    ])
    failure_rate = (failed_count / total_redlines) if total_redlines else 0

    # Fail-loud guard: if we had redline entries but applied zero, the pipeline
    # has a silent contract violation (schema mismatch, missing
    # suggested_redline fields, or total clause-mapping failure). Do not return
    # success — callers must halt.
    success = True
    error_message = None
    if total_redlines > 0 and applied_count == 0:
        success = False
        error_message = (
            'No redlines were applied despite '
            f'{total_redlines} redline entries in the input. '
            'Likely causes: (1) all entries missing "suggested_redline" field, '
            '(2) all clause_ids failed to map to DOCX paragraphs, '
            '(3) clause-map.json is empty or mismatched. '
            'Check Step 7 output schema and Step 8 mapping coverage.'
        )
    elif failed_critical_or_high > 0:
        success = False
        error_message = (
            f'{failed_critical_or_high} Critical/High redline(s) failed to apply. '
            'Pipeline must halt so high-risk edits are not silently dropped.'
        )
    elif total_redlines > 0 and failure_rate > FAILURE_RATE_THRESHOLD:
        success = False
        error_message = (
            f'{failed_count} of {total_redlines} redline entries failed '
            f'({failure_rate:.0%}), exceeding the {FAILURE_RATE_THRESHOLD:.0%} threshold.'
        )
    elif total_redlines == 0:
        # No redlines to apply at all. This is a legitimate "nothing to do"
        # case, so we warn but do not halt.
        error_message = 'Input redlines.json contains zero entries (excluding _meta).'

    return {
        'success': success,
        'error': error_message,
        'output_path': output_path,
        'applied_count': applied_count,
        'failed_count': failed_count,
        'total_entries': total_redlines,
        'applied_entries': applied_count,
        'failed_entries': failed_count,
        'failed_critical_or_high': failed_critical_or_high,
        'failure_rate': round(failure_rate, 3),
        'failures': failures,
        'total_redlines': total_redlines,
        'paragraphs_touched': paragraphs_touched,
        'reviewer': reviewer,
    }


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

#!/usr/bin/env python3
"""
MD clause → DOCX paragraph position mapping.
Maps analyzed clause records back to their corresponding <w:p> positions
in the original DOCX document.xml.
"""

import sys
import os
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}


def extract_docx_paragraphs(docx_path: str) -> list[dict]:
    """Extract all paragraphs from a DOCX file with their positions.

    Returns list of dicts with:
      - index: paragraph index in document.xml body
      - text: extracted text content
      - is_table_cell: whether paragraph is inside a table cell
    """
    with zipfile.ZipFile(docx_path, 'r') as z:
        xml_content = z.read('word/document.xml')

    root = ET.fromstring(xml_content)
    body = root.find(f'{{{NSMAP["w"]}}}body')
    if body is None:
        return []

    paragraphs = []
    idx = 0

    for element in body:
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

        if tag == 'p':
            text = _get_paragraph_text(element)
            paragraphs.append({
                'index': idx,
                'text': text,
                'is_table_cell': False,
            })
            idx += 1

        elif tag == 'tbl':
            # Process table paragraphs
            for tc in element.iter(f'{{{NSMAP["w"]}}}tc'):
                for p in tc.iter(f'{{{NSMAP["w"]}}}p'):
                    text = _get_paragraph_text(p)
                    paragraphs.append({
                        'index': idx,
                        'text': text,
                        'is_table_cell': True,
                    })
                    idx += 1

    return paragraphs


def _get_paragraph_text(p_elem) -> str:
    """Extract text from a <w:p> element."""
    texts = []
    for r in p_elem.iter(f'{{{NSMAP["w"]}}}t'):
        if r.text:
            texts.append(r.text)
    return ''.join(texts).strip()


def normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching."""
    text = re.sub(r'\s+', ' ', text).strip().lower()
    # Remove common punctuation variations
    text = re.sub(r'[""''«»]', '"', text)
    text = re.sub(r'[–—]', '-', text)
    return text


def map_clauses(clauses_dir: str, docx_path: str, output_path: str) -> dict:
    """Map clause records to DOCX paragraph positions.

    Args:
        clauses_dir: directory containing clause-NNN.json files
        docx_path: path to original DOCX file
        output_path: path to write docx-clause-map.json

    Returns:
        dict with mapping results and coverage stats
    """
    # Load DOCX paragraphs
    docx_paragraphs = extract_docx_paragraphs(docx_path)
    if not docx_paragraphs:
        return {'error': 'Failed to extract paragraphs from DOCX', 'success': False}

    # Load clause records
    clause_files = sorted(
        f for f in os.listdir(clauses_dir) if f.endswith('.json')
    )
    if not clause_files:
        return {'error': 'No clause files found', 'success': False}

    # Build mapping
    mappings = []
    mapped_count = 0
    total_count = len(clause_files)

    for cf in clause_files:
        with open(os.path.join(clauses_dir, cf), 'r', encoding='utf-8') as f:
            clause = json.load(f)

        clause_id = clause.get('clause_id', cf.replace('.json', ''))
        clause_text = clause.get('text', '')

        if not clause_text:
            mappings.append({
                'clause_id': clause_id,
                'clause_file': cf,
                'mapped': False,
                'reason': 'Empty clause text',
            })
            continue

        # Find best matching paragraph(s)
        best_matches = _find_matching_paragraphs(clause_text, docx_paragraphs)

        if best_matches:
            mapped_count += 1
            mappings.append({
                'clause_id': clause_id,
                'clause_file': cf,
                'mapped': True,
                'paragraph_indices': [m['index'] for m in best_matches],
                'confidence': best_matches[0].get('similarity', 0),
            })
        else:
            mappings.append({
                'clause_id': clause_id,
                'clause_file': cf,
                'mapped': False,
                'reason': 'No matching paragraph found',
            })

    coverage = mapped_count / total_count if total_count > 0 else 0

    result = {
        'success': True,
        'docx_path': docx_path,
        'total_clauses': total_count,
        'mapped_clauses': mapped_count,
        'coverage': round(coverage, 3),
        'mappings': mappings,
    }

    # Write mapping file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return {
        'success': True,
        'output_path': output_path,
        'total_clauses': total_count,
        'mapped_clauses': mapped_count,
        'coverage': round(coverage, 3),
        'coverage_pct': f"{coverage:.0%}",
    }


def _find_matching_paragraphs(clause_text: str, paragraphs: list[dict]) -> list[dict]:
    """Find the best matching paragraph(s) for a clause text.

    Uses progressive matching: first try exact substring, then fuzzy matching.
    """
    normalized_clause = normalize_for_match(clause_text)

    # Split clause text into sentences for multi-paragraph matching
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', clause_text) if s.strip()]
    first_sentence = normalize_for_match(sentences[0]) if sentences else normalized_clause[:100]

    best_matches = []
    best_similarity = 0.0

    for para in paragraphs:
        if not para['text']:
            continue
        normalized_para = normalize_for_match(para['text'])

        # Try exact substring match first
        if first_sentence and first_sentence in normalized_para:
            return [{'index': para['index'], 'similarity': 1.0, 'text': para['text']}]

        # Try fuzzy matching
        # For long clause texts, compare first 200 chars
        compare_clause = normalized_clause[:200]
        compare_para = normalized_para[:200]

        sim = SequenceMatcher(None, compare_clause, compare_para).ratio()
        if sim > best_similarity and sim > 0.4:
            best_similarity = sim
            best_matches = [{'index': para['index'], 'similarity': sim, 'text': para['text']}]

    return best_matches


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            'error': 'Usage: map-clauses-to-docx.py <clauses_dir> <docx_path> <output_path>'
        }))
        sys.exit(1)

    result = map_clauses(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get('success'):
        sys.exit(1)
    if result.get('coverage', 0) < 0.9:
        sys.exit(2)  # Warning: coverage below 90%


if __name__ == '__main__':
    main()

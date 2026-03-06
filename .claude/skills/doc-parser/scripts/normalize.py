#!/usr/bin/env python3
"""
Document normalization: Convert DOCX/PDF/HTML/TXT/MD to clean.md and plain.txt.

Conversion strategies:
  - DOCX: unzip and parse document.xml, preserving headings, lists, and tables
  - PDF: try pdftotext; fallback to basic text extraction
  - MD: copy as-is for clean.md, strip markdown for plain.txt
  - TXT: copy as-is for plain.txt, wrap in markdown for clean.md
  - HTML: strip tags, preserve structure
"""

import sys
import os
import json
import re
import zipfile
import html
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# OOXML namespaces
NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
}

HEADING_STYLES = {
    'Heading1': '# ', 'Heading2': '## ', 'Heading3': '### ',
    'Heading4': '#### ', 'Heading5': '##### ', 'Heading6': '###### ',
    'heading 1': '# ', 'heading 2': '## ', 'heading 3': '### ',
    'heading 4': '#### ', 'heading 5': '##### ', 'heading 6': '###### ',
    'Title': '# ', 'Subtitle': '## ',
}


def extract_docx_text(file_path: str) -> str:
    """Extract text from DOCX by parsing document.xml."""
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            if 'word/document.xml' not in z.namelist():
                return None
            xml_content = z.read('word/document.xml')
    except (zipfile.BadZipFile, KeyError):
        return None

    root = ET.fromstring(xml_content)
    body = root.find(f'{{{NSMAP["w"]}}}body')
    if body is None:
        return None

    lines = []
    for element in body:
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

        if tag == 'p':
            line = _process_paragraph(element)
            if line is not None:
                lines.append(line)
        elif tag == 'tbl':
            table_lines = _process_table(element)
            lines.extend(table_lines)

    return '\n'.join(lines)


def _process_paragraph(p_elem) -> str | None:
    """Process a single <w:p> paragraph element."""
    # Check for heading style
    prefix = ''
    pPr = p_elem.find(f'{{{NSMAP["w"]}}}pPr')
    if pPr is not None:
        pStyle = pPr.find(f'{{{NSMAP["w"]}}}pStyle')
        if pStyle is not None:
            style_val = pStyle.get(f'{{{NSMAP["w"]}}}val', '')
            prefix = HEADING_STYLES.get(style_val, '')

        # Check for numbered list
        numPr = pPr.find(f'{{{NSMAP["w"]}}}numPr')
        if numPr is not None and not prefix:
            ilvl = numPr.find(f'{{{NSMAP["w"]}}}ilvl')
            level = int(ilvl.get(f'{{{NSMAP["w"]}}}val', '0')) if ilvl is not None else 0
            prefix = '  ' * level + '- '

    # Extract text runs
    texts = []
    for r in p_elem.iter(f'{{{NSMAP["w"]}}}t'):
        if r.text:
            texts.append(r.text)

    text = ''.join(texts).strip()
    if not text and not prefix:
        return ''

    return prefix + text


def _process_table(tbl_elem) -> list[str]:
    """Process a <w:tbl> table element into markdown table format."""
    rows = []
    for tr in tbl_elem.iter(f'{{{NSMAP["w"]}}}tr'):
        cells = []
        for tc in tr.iter(f'{{{NSMAP["w"]}}}tc'):
            cell_texts = []
            for p in tc.iter(f'{{{NSMAP["w"]}}}p'):
                line = _process_paragraph(p)
                if line:
                    cell_texts.append(line)
            cells.append(' '.join(cell_texts))
        rows.append(cells)

    if not rows:
        return []

    lines = []
    # Header row
    lines.append('| ' + ' | '.join(rows[0]) + ' |')
    lines.append('| ' + ' | '.join(['---'] * len(rows[0])) + ' |')
    # Data rows
    for row in rows[1:]:
        # Pad row if shorter than header
        while len(row) < len(rows[0]):
            row.append('')
        lines.append('| ' + ' | '.join(row[:len(rows[0])]) + ' |')

    return ['', *lines, '']


def extract_pdf_text(file_path: str) -> str | None:
    """Extract text from PDF using pdftotext or fallback."""
    # Try pdftotext first
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', file_path, '-'],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: try pymupdf
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return '\n'.join(text_parts)
    except ImportError:
        pass

    # Fallback: try pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or '')
        return '\n'.join(text_parts)
    except ImportError:
        pass

    return None


def strip_html_tags(html_text: str) -> str:
    """Convert HTML to plain text preserving basic structure."""
    # Replace block elements with newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', html_text, flags=re.I)
    text = re.sub(r'</(p|div|li|tr|h[1-6])>', '\n', text, flags=re.I)
    text = re.sub(r'<h([1-6])[^>]*>', lambda m: '#' * int(m.group(1)) + ' ', text, flags=re.I)
    text = re.sub(r'<li[^>]*>', '- ', text, flags=re.I)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text


def strip_markdown(md_text: str) -> str:
    """Strip markdown formatting to produce plain text."""
    text = md_text
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Remove links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove table separators
    text = re.sub(r'^\|[-:| ]+\|$', '', text, flags=re.MULTILINE)
    # Clean up pipes in tables
    text = re.sub(r'\|', ' ', text)
    return text


def normalize(file_path: str, output_dir: str) -> dict:
    """Normalize a document to clean.md and plain.txt.

    Args:
        file_path: path to the source file
        output_dir: directory to write normalized outputs

    Returns:
        dict with normalization result
    """
    result = {
        'source_file': os.path.abspath(file_path),
        'output_dir': os.path.abspath(output_dir),
        'clean_md': None,
        'plain_txt': None,
        'source_length': 0,
        'output_length': 0,
        'heading_count': 0,
        'success': False,
        'error': None,
    }

    if not os.path.exists(file_path):
        result['error'] = f"File not found: {file_path}"
        return result

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    result['source_length'] = os.path.getsize(file_path)

    # Extract text based on format
    md_text = None
    plain_text = None

    if ext == '.docx':
        md_text = extract_docx_text(file_path)
        if md_text is None:
            result['error'] = "Failed to extract text from DOCX"
            return result

    elif ext == '.pdf':
        raw_text = extract_pdf_text(file_path)
        if raw_text is None:
            result['error'] = "Failed to extract text from PDF. Install pdftotext, pymupdf, or pypdf."
            return result
        md_text = raw_text
        plain_text = raw_text

    elif ext == '.md':
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            md_text = f.read()

    elif ext in ('.txt',):
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            plain_text = f.read()
        md_text = plain_text

    elif ext in ('.html', '.htm'):
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            html_content = f.read()
        md_text = strip_html_tags(html_content)

    else:
        result['error'] = f"Unsupported extension: {ext}"
        return result

    # Generate missing formats
    if md_text and not plain_text:
        plain_text = strip_markdown(md_text)
    elif plain_text and not md_text:
        md_text = plain_text

    # Count headings in md_text
    heading_count = len(re.findall(r'^#{1,6}\s+', md_text, re.MULTILINE))
    result['heading_count'] = heading_count

    # Validate output quality
    output_len = len(md_text.encode('utf-8'))
    result['output_length'] = output_len

    if result['source_length'] > 0:
        ratio = output_len / result['source_length']
        # For binary formats, extracted text is usually shorter
        min_ratio = 0.1 if ext in ('.docx', '.pdf') else 0.5
        if ratio < min_ratio:
            result['error'] = f"Excessive text loss during normalization (ratio: {ratio:.2f})"
            return result

    # Write outputs
    os.makedirs(output_dir, exist_ok=True)
    clean_md_path = os.path.join(output_dir, 'clean.md')
    plain_txt_path = os.path.join(output_dir, 'plain.txt')

    with open(clean_md_path, 'w', encoding='utf-8') as f:
        f.write(md_text)
    with open(plain_txt_path, 'w', encoding='utf-8') as f:
        f.write(plain_text)

    result['clean_md'] = clean_md_path
    result['plain_txt'] = plain_txt_path
    result['success'] = True
    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: normalize.py <file_path> <output_dir>'}))
        sys.exit(1)

    file_path = sys.argv[1]
    output_dir = sys.argv[2]
    result = normalize(file_path, output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result['success']:
        sys.exit(1)


if __name__ == '__main__':
    main()

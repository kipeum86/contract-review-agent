#!/usr/bin/env python3
"""
File format detection for contract documents.
Validates that files are supported formats and checks basic integrity.
"""

import sys
import os
import json
import mimetypes

SUPPORTED_FORMATS = {
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.pdf': 'application/pdf',
    '.md': 'text/markdown',
    '.txt': 'text/plain',
    '.html': 'text/html',
    '.htm': 'text/html',
}

# Magic bytes for binary format validation
MAGIC_BYTES = {
    '.docx': b'PK',      # ZIP archive (OOXML)
    '.pdf': b'%PDF',
    '.doc': b'\xd0\xcf',  # OLE2 Compound Document
}


def detect_format(file_path: str) -> dict:
    """Detect and validate a file's format.

    Returns a dict with:
      - path: absolute file path
      - filename: basename
      - extension: file extension (lowercase)
      - mime_type: detected MIME type
      - size_bytes: file size
      - supported: bool
      - error: error message if any
    """
    result = {
        'path': os.path.abspath(file_path),
        'filename': os.path.basename(file_path),
        'extension': None,
        'mime_type': None,
        'size_bytes': 0,
        'supported': False,
        'error': None,
    }

    if not os.path.exists(file_path):
        result['error'] = f"File not found: {file_path}"
        return result

    if not os.path.isfile(file_path):
        result['error'] = f"Not a file: {file_path}"
        return result

    result['size_bytes'] = os.path.getsize(file_path)
    if result['size_bytes'] == 0:
        result['error'] = "File is empty (0 bytes)"
        return result

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    result['extension'] = ext

    if ext not in SUPPORTED_FORMATS:
        result['error'] = f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS.keys())}"
        return result

    # Validate magic bytes for binary formats
    if ext in MAGIC_BYTES:
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
            expected = MAGIC_BYTES[ext]
            if not header.startswith(expected):
                result['error'] = f"File header mismatch for {ext}. File may be corrupt or mislabeled."
                return result
        except IOError as e:
            result['error'] = f"Cannot read file: {e}"
            return result

    result['mime_type'] = SUPPORTED_FORMATS[ext]
    result['supported'] = True
    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: detect-format.py <file_path> [file_path2 ...]'}))
        sys.exit(1)

    results = []
    for path in sys.argv[1:]:
        results.append(detect_format(path))

    print(json.dumps(results, indent=2, ensure_ascii=False))

    # Exit with error if any file is unsupported
    if any(not r['supported'] for r in results):
        sys.exit(1)


if __name__ == '__main__':
    main()

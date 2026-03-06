#!/usr/bin/env python3
"""
SHA-256 fingerprinting and doc_id generation.
Computes content hash and checks for duplicates against documents.json index.
"""

import sys
import os
import json
import hashlib
import re
from datetime import datetime, timezone

# Path to project root is derived from script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
INDEXES_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library', 'indexes')
DOCUMENTS_INDEX = os.path.join(INDEXES_DIR, 'documents.json')


def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def generate_doc_id(filename: str) -> str:
    """Generate a provisional doc_id from filename and timestamp.

    Format: sanitized-filename-YYYYMMDD-HHMMSS
    """
    name = os.path.splitext(filename)[0]
    # Sanitize: lowercase, replace non-alphanumeric with hyphens
    sanitized = re.sub(r'[^a-z0-9가-힣]', '-', name.lower())
    sanitized = re.sub(r'-+', '-', sanitized).strip('-')
    # Truncate long names
    if len(sanitized) > 50:
        sanitized = sanitized[:50].rstrip('-')
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    return f"{sanitized}-{timestamp}"


def load_documents_index() -> dict:
    """Load the documents.json index."""
    if not os.path.exists(DOCUMENTS_INDEX):
        return {'version': 1, 'updated_at': None, 'documents': []}
    with open(DOCUMENTS_INDEX, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_duplicate(sha256: str, index: dict) -> dict | None:
    """Check if a document with the same hash already exists.

    Returns the existing document entry if found, None otherwise.
    """
    for doc in index.get('documents', []):
        if doc.get('sha256') == sha256:
            return doc
    return None


def fingerprint(file_path: str) -> dict:
    """Compute fingerprint and check for duplicates.

    Returns:
      - doc_id: provisional document ID
      - sha256: content hash
      - filename: original filename
      - is_duplicate: bool
      - duplicate_of: doc_id of existing document if duplicate
      - error: error message if any
    """
    result = {
        'doc_id': None,
        'sha256': None,
        'filename': os.path.basename(file_path),
        'file_path': os.path.abspath(file_path),
        'is_duplicate': False,
        'duplicate_of': None,
        'error': None,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }

    if not os.path.exists(file_path):
        result['error'] = f"File not found: {file_path}"
        return result

    try:
        sha256 = compute_sha256(file_path)
    except IOError as e:
        result['error'] = f"Cannot read file: {e}"
        return result

    result['sha256'] = sha256
    result['doc_id'] = generate_doc_id(result['filename'])

    # Check for duplicates
    index = load_documents_index()
    existing = check_duplicate(sha256, index)
    if existing:
        result['is_duplicate'] = True
        result['duplicate_of'] = existing.get('doc_id')

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: fingerprint.py <file_path>'}))
        sys.exit(1)

    file_path = sys.argv[1]
    result = fingerprint(file_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get('is_duplicate'):
        sys.exit(2)  # Exit code 2 = duplicate found
    if result.get('error'):
        sys.exit(1)


if __name__ == '__main__':
    main()

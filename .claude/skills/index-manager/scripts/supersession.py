#!/usr/bin/env python3
"""
Supersession chain management.
Handles marking documents as superseded and maintaining successor chains.
"""

import sys
import os
import json
from datetime import datetime, timezone

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
LIBRARY_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library')
INDEXES_DIR = os.path.join(LIBRARY_DIR, 'indexes')
APPROVED_DIR = os.path.join(LIBRARY_DIR, 'approved')


def load_json(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def find_manifest(doc_id: str) -> str | None:
    """Find the manifest.yaml for a given doc_id under approved/."""
    import glob
    pattern = os.path.join(APPROVED_DIR, '**', 'manifest.yaml')
    for mp in glob.glob(pattern, recursive=True):
        m = load_yaml(mp)
        if m and m.get('doc_id') == doc_id:
            return mp
    return None


def supersede(old_doc_id: str, new_doc_id: str) -> dict:
    """Mark old_doc_id as superseded by new_doc_id.

    Updates both manifests and the supersession index.
    """
    old_manifest_path = find_manifest(old_doc_id)
    new_manifest_path = find_manifest(new_doc_id)

    if not old_manifest_path:
        return {'error': f'Document not found: {old_doc_id}'}
    if not new_manifest_path:
        return {'error': f'Document not found: {new_doc_id}'}

    # Update old manifest
    old_manifest = load_yaml(old_manifest_path)
    old_manifest['status'] = 'superseded'
    old_manifest['superseded_by'] = new_doc_id
    old_manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_yaml(old_manifest_path, old_manifest)

    # Update new manifest
    new_manifest = load_yaml(new_manifest_path)
    new_manifest['supersedes'] = old_doc_id
    new_manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_yaml(new_manifest_path, new_manifest)

    # Update supersession index
    sup_index = load_json(os.path.join(INDEXES_DIR, 'supersession.json')) or {
        'version': 1, 'updated_at': None, 'chains': []
    }

    # Remove any existing entries for these doc_ids
    sup_index['chains'] = [
        c for c in sup_index['chains']
        if c.get('doc_id') not in (old_doc_id, new_doc_id)
    ]

    # Add updated entries
    sup_index['chains'].append({
        'doc_id': old_doc_id,
        'supersedes': old_manifest.get('supersedes'),
        'superseded_by': new_doc_id,
        'status': 'superseded',
    })
    sup_index['chains'].append({
        'doc_id': new_doc_id,
        'supersedes': old_doc_id,
        'superseded_by': None,
        'status': new_manifest.get('status', 'active'),
    })
    sup_index['updated_at'] = datetime.now(timezone.utc).isoformat()

    save_json(os.path.join(INDEXES_DIR, 'supersession.json'), sup_index)

    return {
        'success': True,
        'old_doc_id': old_doc_id,
        'new_doc_id': new_doc_id,
        'message': f'{old_doc_id} is now superseded by {new_doc_id}',
    }


def get_chain(doc_id: str) -> dict:
    """Get the full supersession chain for a document."""
    sup_index = load_json(os.path.join(INDEXES_DIR, 'supersession.json'))
    if not sup_index:
        return {'chain': [], 'doc_id': doc_id}

    chains = {c['doc_id']: c for c in sup_index.get('chains', [])}

    # Walk backwards to find the root
    current = doc_id
    visited = set()
    while current in chains and chains[current].get('supersedes') and current not in visited:
        visited.add(current)
        current = chains[current]['supersedes']

    # Walk forwards from root
    chain = []
    visited = set()
    while current and current not in visited:
        visited.add(current)
        entry = chains.get(current, {'doc_id': current})
        chain.append(entry)
        current = entry.get('superseded_by')

    return {'doc_id': doc_id, 'chain': chain}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: supersession.py <supersede|chain> [args]'}))
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'supersede' and len(sys.argv) == 4:
        result = supersede(sys.argv[2], sys.argv[3])
    elif mode == 'chain' and len(sys.argv) == 3:
        result = get_chain(sys.argv[2])
    else:
        result = {'error': 'Usage: supersession.py supersede <old_id> <new_id> | chain <doc_id>'}

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get('error'):
        sys.exit(1)


if __name__ == '__main__':
    main()

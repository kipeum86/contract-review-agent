#!/usr/bin/env python3
"""
Index build and refresh.
Scans approved/ directory and rebuilds all index files:
  - documents.json
  - clauses.json
  - terms.json
  - retrieval-map.json
  - supersession.json
"""

import sys
import os
import json
import glob
from datetime import datetime, timezone

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
LIBRARY_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library')
APPROVED_DIR = os.path.join(LIBRARY_DIR, 'approved')
INDEXES_DIR = os.path.join(LIBRARY_DIR, 'indexes')


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_json(path: str) -> dict | list | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_index(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_manifests(base_dir: str) -> list[str]:
    """Find all manifest.yaml files under the given directory."""
    pattern = os.path.join(base_dir, '**', 'manifest.yaml')
    return glob.glob(pattern, recursive=True)


def build_documents_index(manifests: list[dict]) -> dict:
    """Build documents.json from manifest data."""
    documents = []
    for m in manifests:
        doc_entry = {
            'doc_id': m.get('doc_id'),
            'title': m.get('title'),
            'doc_class': m.get('doc_class'),
            'contract_family': m.get('contract_family'),
            'subtype': m.get('subtype'),
            'paper_role': m.get('paper_role'),
            'jurisdiction': m.get('jurisdiction'),
            'governing_law': m.get('governing_law'),
            'language': m.get('language'),
            'authority_level': m.get('authority_level'),
            'approval_state': m.get('approval_state'),
            'status': m.get('status'),
            'external_safe': m.get('external_safe', False),
            'freshness_sensitive': m.get('freshness_sensitive', False),
            'last_legal_refresh_date': m.get('last_legal_refresh_date'),
            'sha256': m.get('sha256'),
            'source_file': m.get('source_file'),
            'supersedes': m.get('supersedes'),
            'superseded_by': m.get('superseded_by'),
            'created_at': m.get('created_at'),
            'updated_at': m.get('updated_at'),
            'manifest_path': m.get('_manifest_path'),
        }
        documents.append(doc_entry)

    return {
        'version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'documents': documents,
    }


def build_clauses_index(manifests: list[dict]) -> dict:
    """Build clauses.json by collecting all clause records from approved documents."""
    clauses = []
    for m in manifests:
        doc_id = m.get('doc_id')
        manifest_path = m.get('_manifest_path')
        if not manifest_path:
            continue
        doc_dir = os.path.dirname(manifest_path)
        clauses_dir = os.path.join(doc_dir, 'clauses')
        if not os.path.isdir(clauses_dir):
            continue
        for clause_file in sorted(os.listdir(clauses_dir)):
            if not clause_file.endswith('.json'):
                continue
            clause_path = os.path.join(clauses_dir, clause_file)
            clause_data = load_json(clause_path)
            if clause_data:
                clause_data['doc_id'] = doc_id
                clause_data['contract_family'] = m.get('contract_family')
                clause_data['jurisdiction'] = m.get('jurisdiction')
                clause_data['governing_law'] = m.get('governing_law')
                clause_data['approval_state'] = m.get('approval_state', 'approved')
                clause_data['status'] = m.get('status', 'active')
                clause_data['authority_level'] = m.get('authority_level')
                clause_data['external_safe'] = m.get('external_safe', False)
                clause_data['freshness_sensitive'] = m.get('freshness_sensitive', False)
                clause_data['last_legal_refresh_date'] = m.get('last_legal_refresh_date')
                clauses.append(clause_data)

    return {
        'version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'clauses': clauses,
    }


def build_terms_index(manifests: list[dict]) -> dict:
    """Build terms.json from defined_terms.json in each document."""
    terms = []
    for m in manifests:
        doc_id = m.get('doc_id')
        manifest_path = m.get('_manifest_path')
        if not manifest_path:
            continue
        doc_dir = os.path.dirname(manifest_path)
        terms_path = os.path.join(doc_dir, 'structure', 'defined_terms.json')
        terms_data = load_json(terms_path)
        if terms_data and isinstance(terms_data, list):
            for term in terms_data:
                term['doc_id'] = doc_id
                terms.append(term)

    return {
        'version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'terms': terms,
    }


def build_retrieval_map(clauses_index: dict) -> dict:
    """Build retrieval-map.json for quick clause lookup by type and family."""
    mappings = {}
    for clause in clauses_index.get('clauses', []):
        family = clause.get('contract_family', 'unknown')
        ctype = clause.get('clause_type', 'unmapped')
        key = f"{family}:{ctype}"
        if key not in mappings:
            mappings[key] = []
        mappings[key].append({
            'clause_id': clause.get('clause_id'),
            'doc_id': clause.get('doc_id'),
            'authority_level': clause.get('authority_level'),
            'section_no': clause.get('section_no'),
            'heading': clause.get('heading'),
        })

    return {
        'version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'mappings': [
            {'key': k, 'clauses': v} for k, v in sorted(mappings.items())
        ],
    }


def build_supersession_index(manifests: list[dict]) -> dict:
    """Build supersession.json tracking supersession chains."""
    chains = []
    for m in manifests:
        if m.get('supersedes') or m.get('superseded_by'):
            chains.append({
                'doc_id': m.get('doc_id'),
                'supersedes': m.get('supersedes'),
                'superseded_by': m.get('superseded_by'),
                'status': m.get('status'),
            })

    return {
        'version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'chains': chains,
    }


def register_document(manifest_path: str) -> dict:
    """Register a single document by adding it to indexes.

    Used during the publish step (Step 10) to add a newly approved document.
    """
    manifest = load_yaml(manifest_path)
    if not manifest:
        return {'error': f'Cannot load manifest: {manifest_path}'}

    manifest['_manifest_path'] = manifest_path

    # Load existing indexes
    docs_index = load_json(os.path.join(INDEXES_DIR, 'documents.json')) or {
        'version': 1, 'updated_at': None, 'documents': []
    }

    # Check if already registered
    doc_id = manifest.get('doc_id')
    existing_ids = {d.get('doc_id') for d in docs_index.get('documents', [])}
    if doc_id in existing_ids:
        return {'error': f'Document {doc_id} already registered', 'doc_id': doc_id}

    # Full rebuild is simpler and ensures consistency
    return rebuild_all()


def rebuild_all() -> dict:
    """Full rebuild of all indexes from approved/ directory."""
    manifest_paths = find_manifests(APPROVED_DIR)
    manifests = []
    for mp in manifest_paths:
        m = load_yaml(mp)
        if m:
            m['_manifest_path'] = mp
            manifests.append(m)

    docs_index = build_documents_index(manifests)
    clauses_index = build_clauses_index(manifests)
    terms_index = build_terms_index(manifests)
    retrieval_map = build_retrieval_map(clauses_index)
    supersession_index = build_supersession_index(manifests)

    save_index(os.path.join(INDEXES_DIR, 'documents.json'), docs_index)
    save_index(os.path.join(INDEXES_DIR, 'clauses.json'), clauses_index)
    save_index(os.path.join(INDEXES_DIR, 'terms.json'), terms_index)
    save_index(os.path.join(INDEXES_DIR, 'retrieval-map.json'), retrieval_map)
    save_index(os.path.join(INDEXES_DIR, 'supersession.json'), supersession_index)

    return {
        'success': True,
        'documents_count': len(docs_index['documents']),
        'clauses_count': len(clauses_index['clauses']),
        'terms_count': len(terms_index['terms']),
        'retrieval_mappings': len(retrieval_map['mappings']),
        'supersession_chains': len(supersession_index['chains']),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'rebuild'

    if mode == 'rebuild':
        result = rebuild_all()
    elif mode == 'register' and len(sys.argv) > 2:
        result = register_document(sys.argv[2])
    else:
        result = {'error': 'Usage: build-index.py [rebuild|register <manifest_path>]'}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get('error'):
        sys.exit(1)


if __name__ == '__main__':
    main()

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
INDEX_VERSION = 2


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as exc:
        print(f"[build-index] skipping unreadable YAML {path}: {exc}", file=sys.stderr)
        return None


def load_json(path: str) -> dict | list | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[build-index] skipping unreadable JSON {path}: {exc}", file=sys.stderr)
        return None


def save_index(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def to_library_relative_path(abs_path: str) -> str:
    rel_path = os.path.relpath(abs_path, LIBRARY_DIR)
    rel_path = rel_path.replace(os.sep, '/')
    if os.path.isdir(abs_path) and not rel_path.endswith('/'):
        rel_path += '/'
    return rel_path


def normalize_clause_record(clause_data: dict, manifest: dict, clause_path: str) -> dict | None:
    """Normalize a clause record for indexing.

    Approved indexes should only contain clause rows with enough metadata to support
    deterministic retrieval and downstream semantic matching.
    """
    if not isinstance(clause_data, dict):
        return None

    clause_id = clause_data.get('clause_id')
    clause_type = clause_data.get('clause_type')
    text = clause_data.get('text')
    heading = clause_data.get('heading') or clause_data.get('header')

    if not clause_id or not clause_type or not text or not heading:
        return None

    return {
        'doc_id': manifest.get('doc_id'),
        'clause_id': clause_id,
        'doc_class': manifest.get('doc_class'),
        'section_no': clause_data.get('section_no'),
        'heading': heading,
        'header': clause_data.get('header', heading),
        'clause_type': clause_type,
        'text': text,
        'defined_terms_used': clause_data.get('defined_terms_used', []),
        'cross_refs': clause_data.get('cross_refs', []),
        'paragraph_count': clause_data.get('paragraph_count'),
        'start_line': clause_data.get('start_line'),
        'end_line': clause_data.get('end_line'),
        'char_count': clause_data.get('char_count', len(text)),
        'contract_family': manifest.get('contract_family'),
        'jurisdiction': manifest.get('jurisdiction'),
        'governing_law': manifest.get('governing_law'),
        'language': manifest.get('language'),
        'authority_level': manifest.get('authority_level'),
        'approval_state': manifest.get('approval_state', 'approved'),
        'status': manifest.get('status', 'active'),
        'external_safe': manifest.get('external_safe', False),
        'freshness_sensitive': manifest.get('freshness_sensitive', False),
        'last_legal_refresh_date': manifest.get('last_legal_refresh_date'),
        'document_path': to_library_relative_path(os.path.dirname(clause_path)),
        'manifest_path': to_library_relative_path(manifest.get('_manifest_path')),
    }


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
            'path': to_library_relative_path(os.path.dirname(m.get('_manifest_path'))),
            'supersedes': m.get('supersedes'),
            'superseded_by': m.get('superseded_by'),
            'created_at': m.get('created_at'),
            'updated_at': m.get('updated_at'),
            'manifest_path': to_library_relative_path(m.get('_manifest_path')),
        }
        documents.append(doc_entry)

    return {
        'version': INDEX_VERSION,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'documents': documents,
    }


def build_clauses_index(manifests: list[dict]) -> tuple[dict, dict]:
    """Build clauses.json (metadata only) and clause-texts.json (text lookup).

    Returns a tuple of (clauses_index, clause_texts_index).
    clauses_index contains all clause metadata without the 'text' field.
    clause_texts_index maps 'doc_id::clause_id' to the clause text for lazy loading.
    """
    clauses = []
    texts = {}
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
            normalized = normalize_clause_record(clause_data, m, clause_path)
            if normalized:
                text = normalized.pop('text', '')
                text_key = f"{normalized['doc_id']}::{normalized['clause_id']}"
                texts[text_key] = text
                clauses.append(normalized)

    now = datetime.now(timezone.utc).isoformat()
    clauses_index = {
        'version': INDEX_VERSION,
        'updated_at': now,
        'clauses': clauses,
    }
    clause_texts_index = {
        'version': INDEX_VERSION,
        'updated_at': now,
        'texts': texts,
    }
    return clauses_index, clause_texts_index


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
                term = dict(term)
                term['doc_id'] = doc_id
                terms.append(term)

    return {
        'version': INDEX_VERSION,
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
        'version': INDEX_VERSION,
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
        'version': INDEX_VERSION,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'chains': chains,
    }


def build_redline_patterns_index(manifests: list[dict]) -> dict:
    """Build redline-patterns.json from redline_record documents.

    Scans clauses in redline_record packages for redline_data.review_pattern
    and groups them by {contract_family}:{clause_type} for retrieval.
    """
    redline_manifests = [m for m in manifests if m.get('doc_class') == 'redline_record']
    entries_map = {}

    for m in redline_manifests:
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
            clause_data = load_json(os.path.join(clauses_dir, clause_file))
            if not clause_data:
                continue

            redline_data = clause_data.get('redline_data')
            if not redline_data or not redline_data.get('has_changes'):
                continue

            family = m.get('contract_family', 'unknown')
            clause_type = clause_data.get('clause_type', 'unmapped')
            key = f"{family}:{clause_type}"

            review_pattern = redline_data.get('review_pattern', {})
            record = {
                'doc_id': doc_id,
                'clause_id': clause_data.get('clause_id'),
                'base_template_id': m.get('base_template_id'),
                'pattern_type': review_pattern.get('pattern_type'),
                'change_summary': review_pattern.get('description', ''),
                'reviewer': m.get('reviewer'),
                'counterparty': m.get('counterparty'),
                'date': m.get('created_at', '')[:10] if m.get('created_at') else '',
                'clause_path': to_library_relative_path(
                    os.path.join(clauses_dir, clause_file)
                ),
            }

            if key not in entries_map:
                entries_map[key] = []
            entries_map[key].append(record)

    return {
        'version': INDEX_VERSION,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'entries': [
            {'key': k, 'records': v} for k, v in sorted(entries_map.items())
        ],
    }


def build_negotiation_history_index(manifests: list[dict]) -> dict:
    """Build negotiation-history.json grouping redline records by deal_id."""
    redline_manifests = [m for m in manifests if m.get('doc_class') == 'redline_record']
    deal_map = {}

    for m in redline_manifests:
        deal_id = m.get('deal_id')
        if not deal_id:
            continue

        if deal_id not in deal_map:
            deal_map[deal_id] = {
                'deal_id': deal_id,
                'contract_family': m.get('contract_family'),
                'counterparty': m.get('counterparty'),
                'rounds': [],
            }

        # Count total changes across clauses
        total_changes = 0
        manifest_path = m.get('_manifest_path')
        if manifest_path:
            report_path = os.path.join(
                os.path.dirname(manifest_path), 'extraction', 'extraction-report.json'
            )
            report = load_json(report_path)
            if report:
                total_changes = report.get('total_changes', 0)

        deal_map[deal_id]['rounds'].append({
            'round': m.get('negotiation_round', 1),
            'doc_id': m.get('doc_id'),
            'date': m.get('created_at', '')[:10] if m.get('created_at') else '',
            'total_changes': total_changes,
        })

    # Sort rounds within each deal
    for deal in deal_map.values():
        deal['rounds'].sort(key=lambda r: r.get('round', 0))

    return {
        'version': INDEX_VERSION,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'histories': list(deal_map.values()),
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
        'version': INDEX_VERSION, 'updated_at': None, 'documents': []
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
    clauses_index, clause_texts_index = build_clauses_index(manifests)
    terms_index = build_terms_index(manifests)
    retrieval_map = build_retrieval_map(clauses_index)
    supersession_index = build_supersession_index(manifests)
    redline_patterns = build_redline_patterns_index(manifests)
    negotiation_history = build_negotiation_history_index(manifests)

    save_index(os.path.join(INDEXES_DIR, 'documents.json'), docs_index)
    save_index(os.path.join(INDEXES_DIR, 'clauses.json'), clauses_index)
    save_index(os.path.join(INDEXES_DIR, 'clause-texts.json'), clause_texts_index)
    save_index(os.path.join(INDEXES_DIR, 'terms.json'), terms_index)
    save_index(os.path.join(INDEXES_DIR, 'retrieval-map.json'), retrieval_map)
    save_index(os.path.join(INDEXES_DIR, 'supersession.json'), supersession_index)
    save_index(os.path.join(INDEXES_DIR, 'redline-patterns.json'), redline_patterns)
    save_index(os.path.join(INDEXES_DIR, 'negotiation-history.json'), negotiation_history)

    return {
        'success': True,
        'documents_count': len(docs_index['documents']),
        'clauses_count': len(clauses_index['clauses']),
        'clause_texts_count': len(clause_texts_index['texts']),
        'terms_count': len(terms_index['terms']),
        'retrieval_mappings': len(retrieval_map['mappings']),
        'supersession_chains': len(supersession_index['chains']),
        'redline_patterns_count': len(redline_patterns['entries']),
        'negotiation_histories_count': len(negotiation_history['histories']),
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

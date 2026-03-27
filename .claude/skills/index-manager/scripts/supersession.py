#!/usr/bin/env python3
"""
Supersession chain management.
Handles marking documents as superseded and maintaining successor chains.
"""

import sys
import os
import json
import tempfile
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=os.path.dirname(path),
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=os.path.dirname(path),
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def supersession_index_path() -> str:
    return os.path.join(INDEXES_DIR, 'supersession.json')


def load_supersession_index() -> dict:
    return load_json(supersession_index_path()) or {
        'version': 1,
        'updated_at': None,
        'chains': [],
    }


def build_chain_lookup(sup_index: dict) -> dict[str, dict]:
    lookup = {}
    for chain in sup_index.get('chains', []):
        doc_id = chain.get('doc_id')
        if doc_id:
            lookup[doc_id] = chain
    return lookup


def normalize_cycle(cycle_nodes: list[str]) -> tuple[str, ...]:
    nodes = cycle_nodes[:-1] if cycle_nodes and cycle_nodes[0] == cycle_nodes[-1] else cycle_nodes[:]
    if not nodes:
        return tuple()
    rotations = [tuple(nodes[i:] + nodes[:i]) for i in range(len(nodes))]
    return min(rotations)


def find_pointer_cycles(chains: list[dict], field: str) -> list[list[str]]:
    mapping = {
        chain['doc_id']: chain.get(field)
        for chain in chains
        if chain.get('doc_id') and chain.get(field)
    }
    cycles = []
    seen_cycles = set()

    for start in mapping:
        order = []
        positions = {}
        current = start

        while current in mapping:
            if current in positions:
                cycle = order[positions[current]:] + [current]
                normalized = normalize_cycle(cycle)
                if normalized and normalized not in seen_cycles:
                    seen_cycles.add(normalized)
                    cycles.append(cycle)
                break

            positions[current] = len(order)
            order.append(current)
            current = mapping[current]

    return cycles


def write_cycle_diagnostic(diagnostics: dict, report_name: str = 'supersession-cycle-diagnostic.json') -> str:
    report_path = os.path.join(INDEXES_DIR, report_name)
    save_json(report_path, diagnostics)
    return report_path


def diagnose_cycles(sup_index: dict | None = None, write_report: bool = False) -> dict:
    active_index = sup_index or load_supersession_index()
    chains = active_index.get('chains', [])
    supersedes_cycles = find_pointer_cycles(chains, 'supersedes')
    superseded_by_cycles = find_pointer_cycles(chains, 'superseded_by')
    has_cycles = bool(supersedes_cycles or superseded_by_cycles)

    diagnostics = {
        'has_cycles': has_cycles,
        'chain_count': len(chains),
        'supersedes_cycles': supersedes_cycles,
        'superseded_by_cycles': superseded_by_cycles,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }

    if has_cycles and write_report:
        diagnostics['diagnostic_report'] = write_cycle_diagnostic(diagnostics)

    return diagnostics


def has_pointer_ancestor(chains: dict[str, dict], start_doc_id: str, expected_ancestor: str, field: str) -> bool:
    visited = set()
    current = start_doc_id

    while current and current not in visited:
        visited.add(current)
        entry = chains.get(current, {})
        current = entry.get(field)
        if current == expected_ancestor:
            return True

    return False


def merge_chain_entry(existing_entry: dict | None, manifest: dict) -> dict:
    entry = dict(existing_entry or {})
    doc_id = manifest.get('doc_id') or entry.get('doc_id')
    merged = {'doc_id': doc_id}

    for field in ('supersedes', 'superseded_by', 'status'):
        manifest_value = manifest.get(field)
        merged[field] = manifest_value if manifest_value is not None else entry.get(field)

    return merged


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
    if old_doc_id == new_doc_id:
        return {'error': f'Document cannot supersede itself: {old_doc_id}'}

    existing_diagnostics = diagnose_cycles(write_report=True)
    if existing_diagnostics.get('has_cycles'):
        return {
            'error': 'Supersession index already contains cycle(s); repair it before adding new links.',
            'diagnostic_report': existing_diagnostics.get('diagnostic_report'),
        }

    old_manifest_path = find_manifest(old_doc_id)
    new_manifest_path = find_manifest(new_doc_id)

    if not old_manifest_path:
        return {'error': f'Document not found: {old_doc_id}'}
    if not new_manifest_path:
        return {'error': f'Document not found: {new_doc_id}'}

    old_manifest = load_yaml(old_manifest_path)
    new_manifest = load_yaml(new_manifest_path)
    if old_manifest.get('superseded_by') == new_doc_id and new_manifest.get('supersedes') == old_doc_id:
        return {
            'success': True,
            'old_doc_id': old_doc_id,
            'new_doc_id': new_doc_id,
            'message': f'{old_doc_id} is already marked as superseded by {new_doc_id}',
            'no_op': True,
        }

    if old_manifest.get('superseded_by') and old_manifest.get('superseded_by') != new_doc_id:
        return {
            'error': (
                f'Document {old_doc_id} is already superseded by '
                f"{old_manifest.get('superseded_by')}"
            )
        }

    if new_manifest.get('supersedes') and new_manifest.get('supersedes') != old_doc_id:
        return {
            'error': (
                f'Document {new_doc_id} already supersedes '
                f"{new_manifest.get('supersedes')}"
            )
        }

    sup_index = load_supersession_index()
    chain_lookup = build_chain_lookup(sup_index)
    chain_lookup[old_doc_id] = merge_chain_entry(chain_lookup.get(old_doc_id), old_manifest)
    chain_lookup[new_doc_id] = merge_chain_entry(chain_lookup.get(new_doc_id), new_manifest)

    if has_pointer_ancestor(chain_lookup, new_doc_id, old_doc_id, 'supersedes'):
        return {
            'error': (
                f'Cannot mark {old_doc_id} as superseded by {new_doc_id}: '
                f'{new_doc_id} already descends from {old_doc_id}'
            )
        }

    if has_pointer_ancestor(chain_lookup, old_doc_id, new_doc_id, 'superseded_by'):
        return {
            'error': (
                f'Cannot mark {old_doc_id} as superseded by {new_doc_id}: '
                f'{new_doc_id} is already a recorded successor of {old_doc_id}'
            )
        }

    proposed_lookup = dict(chain_lookup)
    proposed_lookup[old_doc_id] = {
        'doc_id': old_doc_id,
        'supersedes': old_manifest.get('supersedes'),
        'superseded_by': new_doc_id,
        'status': 'superseded',
    }
    proposed_lookup[new_doc_id] = {
        'doc_id': new_doc_id,
        'supersedes': old_doc_id,
        'superseded_by': new_manifest.get('superseded_by'),
        'status': new_manifest.get('status', 'active'),
    }

    prospective_diagnostics = diagnose_cycles(
        {
            'version': sup_index.get('version', 1),
            'updated_at': sup_index.get('updated_at'),
            'chains': list(proposed_lookup.values()),
        },
        write_report=False,
    )
    if prospective_diagnostics.get('has_cycles'):
        prospective_diagnostics['diagnostic_report'] = write_cycle_diagnostic(
            prospective_diagnostics,
            report_name='supersession-cycle-diagnostic-proposed.json',
        )
        return {
            'error': 'Requested supersession would create a cycle.',
            'diagnostic_report': prospective_diagnostics['diagnostic_report'],
        }

    old_manifest['status'] = 'superseded'
    old_manifest['superseded_by'] = new_doc_id
    old_manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_yaml(old_manifest_path, old_manifest)

    new_manifest['supersedes'] = old_doc_id
    new_manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_yaml(new_manifest_path, new_manifest)

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

    save_json(supersession_index_path(), sup_index)

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
    elif mode == 'diagnose' and len(sys.argv) == 2:
        result = diagnose_cycles(write_report=True)
    else:
        result = {'error': 'Usage: supersession.py supersede <old_id> <new_id> | chain <doc_id> | diagnose'}

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get('error'):
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Manifest schema validation.
Validates manifest.yaml against the schema defined in metadata-schema.yaml.
"""

import sys
import os
import json
import re
from datetime import datetime

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
POLICIES_DIR = os.path.join(PROJECT_ROOT, 'contract-review', 'library', 'policies')


def load_yaml(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def validate_field(value, field_spec: dict) -> str | None:
    """Validate a single field value against its spec.
    Returns error message or None if valid."""
    field_name = field_spec['field']
    field_type = field_spec.get('type', 'string')

    if value is None:
        return f"Missing required field: {field_name}"

    if field_type == 'string':
        if not isinstance(value, str):
            return f"Field '{field_name}' must be a string, got {type(value).__name__}"
        pattern = field_spec.get('pattern')
        if pattern and not re.match(pattern, value):
            return f"Field '{field_name}' does not match pattern: {pattern}"

    elif field_type == 'enum':
        allowed = field_spec.get('values', [])
        if value not in allowed:
            return f"Field '{field_name}' must be one of {allowed}, got '{value}'"

    elif field_type == 'boolean':
        if not isinstance(value, bool):
            return f"Field '{field_name}' must be boolean, got {type(value).__name__}"

    elif field_type == 'datetime':
        if not isinstance(value, str):
            return f"Field '{field_name}' must be an ISO 8601 string"
        try:
            datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return f"Field '{field_name}' is not a valid ISO 8601 datetime: {value}"

    elif field_type == 'date':
        if not isinstance(value, str):
            return f"Field '{field_name}' must be a date string (YYYY-MM-DD)"

    elif field_type == 'list':
        if not isinstance(value, list):
            return f"Field '{field_name}' must be a list, got {type(value).__name__}"

    elif field_type == 'object':
        if not isinstance(value, dict):
            return f"Field '{field_name}' must be an object, got {type(value).__name__}"

    return None


def validate_manifest(manifest_path: str) -> dict:
    """Validate a manifest.yaml file against the metadata schema.

    Returns:
        dict with validation results:
          - valid: bool
          - errors: list of error messages (hard fails)
          - warnings: list of warning messages (soft fails)
          - missing_required: count of missing required fields
    """
    result = {
        'manifest_path': manifest_path,
        'valid': False,
        'errors': [],
        'warnings': [],
        'missing_required': 0,
    }

    # Load schema
    schema = load_yaml(os.path.join(POLICIES_DIR, 'metadata-schema.yaml'))
    if not schema:
        result['errors'].append('Cannot load metadata-schema.yaml')
        return result

    # Load manifest
    manifest = load_yaml(manifest_path)
    if not manifest:
        result['errors'].append(f'Cannot load manifest: {manifest_path}')
        return result

    manifest_schema = schema.get('manifest_schema', {})

    # Validate required fields
    for field_spec in manifest_schema.get('required_fields', []):
        field_name = field_spec['field']
        value = manifest.get(field_name)
        if value is None:
            result['errors'].append(f"Missing required field: {field_name}")
            result['missing_required'] += 1
        else:
            err = validate_field(value, field_spec)
            if err:
                result['errors'].append(err)

    # Validate optional fields (only if present)
    for field_spec in manifest_schema.get('optional_fields', []):
        field_name = field_spec['field']
        value = manifest.get(field_name)
        if value is not None:
            err = validate_field(value, field_spec)
            if err:
                result['warnings'].append(err)

    # Hard fail if >= 3 required fields missing
    if result['missing_required'] >= 3:
        result['errors'].insert(0, f"HARD FAIL: {result['missing_required']} required fields missing (threshold: 3)")

    result['valid'] = len(result['errors']) == 0
    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: validate-manifest.py <manifest_path>'}))
        sys.exit(1)

    manifest_path = sys.argv[1]
    result = validate_manifest(manifest_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result['valid']:
        sys.exit(1)


if __name__ == '__main__':
    main()

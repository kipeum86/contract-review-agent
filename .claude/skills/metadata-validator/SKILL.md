# metadata-validator Skill

Validate ingestion package integrity, manifest schemas, and detect privileged content.

## Capabilities

1. **Manifest Validation** (`scripts/validate-manifest.py`)
   - Validates `manifest.yaml` against `metadata-schema.yaml`
   - Checks required fields, data types, enum values, patterns
   - Usage: `python3 validate-manifest.py <manifest_path>`

2. **Package Validation** (`scripts/validate-package.py`)
   - Checks complete ingestion package integrity
   - Validates: normalized text, structural parse, manifest, clauses, numbering
   - Applies hard-fail and soft-fail conditions
   - Usage: `python3 validate-package.py <package_dir>`
   - Exit codes: 0=valid, 1=hard fail, 2=soft fail

3. **Privilege Leak Detection** (`scripts/check-privilege-leak.py`)
   - Scans for internal comments, attorney-client privilege markers, strategy notes
   - Supports English and Korean patterns
   - Usage: `python3 check-privilege-leak.py <file_or_dir>`
   - Exit codes: 0=clean, 2=found but isolable, 3=found and cannot isolate

## When to Use

- WF1 Step 8 (Validation & Risk Check): run all three validators
- Before publishing any asset to approved/
- When checking external-safe eligibility

## Hard-Fail Conditions

These cause QUARANTINE:
- Normalized text is absent or empty
- Structural parse output is missing
- Three or more required manifest fields are missing
- Privileged content detected and cannot be isolated
- Source file is corrupt or unreadable

## Soft-Fail Conditions

These cause STAGING (human review):
- Unmapped clauses ≥ 30%
- Defined term extraction failed
- Governing law is ambiguous
- Near-duplicate conflict unresolved
- Freshness-sensitive clause lacks `last_legal_refresh_date`

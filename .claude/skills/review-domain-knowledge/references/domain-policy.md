# Contract Review Domain Policy

## Document Lifecycle

```
inbox/raw → ingestion pipeline → staging/ → approval → approved/
                                     ↓                      ↓
                                 quarantine/            archive/ (deprecated)
```

### Approval States
- **pending**: Just entered the system, not yet processed
- **staging**: Passed validation, awaiting human review
- **approved**: Published to the library, available for retrieval
- **quarantined**: Failed hard validation or rejected
- **archived**: Removed from active use

### Status Values
- **active**: Current and available for matching
- **deprecated**: Outdated but retained for reference
- **superseded**: Replaced by a newer version (successor exists)
- **archived**: Moved to archive, excluded from indexes

## Document Classes

| Class | Description | Ingestion Target |
|-------|-------------|------------------|
| `template` | Organization's standard contract form | `approved/templates/{family}/{doc_id}/` |
| `precedent` | Previously executed contract for reference | `approved/precedents/{doc_id}/` |
| `playbook` | Clause-level negotiation policy (YAML) | `approved/playbooks/` |
| `comment_bank` | Reusable comment library (YAML) | `approved/comment-bank/{audience}/` |
| `review_target` | Contract under review (not a library asset) | `matters/{matter_id}/round_{N}/` |

## Authority Levels

Used for retrieval priority and clause selection:
1. **preferred**: First choice; represents the ideal house position
2. **acceptable**: Tolerable alternative; used when preferred is not available
3. **fallback**: Maximum concession; last resort before rejecting
4. **reference_only**: For information only; not used as authoritative guidance

## External Safety

The `external_safe` flag controls whether content can appear in counterparty-facing output:
- `true`: Content may be referenced in `[EXTERNAL]` comments and external-clean DOCX
- `false` (default): Content is internal-only

This flag must be explicitly set. It defaults to `false` for safety.

## Freshness Management

Certain clause types are freshness-sensitive (e.g., data protection, regulatory compliance).
- Mark with `freshness_sensitive: true` in the manifest
- Set `last_legal_refresh_date` to the date of last legal review
- Stale records (older than threshold in `retrieval-priority.yaml`) are downranked or excluded

## Folder Schema

```
library/
├── inbox/raw/              # User drops files here
├── inbox/sidecars/         # Optional metadata YAML files
├── staging/{doc_id}/       # Awaiting approval
│   ├── manifest.yaml
│   ├── normalized/
│   ├── structure/
│   ├── clauses/
│   └── quality/
├── quarantine/{doc_id}/    # Failed or rejected
├── approved/
│   ├── templates/{family}/{doc_id}/
│   ├── precedents/{doc_id}/
│   ├── precedents/reference-only/{doc_id}/
│   ├── playbooks/
│   ├── comment-bank/external/
│   ├── comment-bank/internal/
│   └── clause-bank/
├── indexes/
│   ├── documents.json
│   ├── clauses.json
│   ├── terms.json
│   ├── retrieval-map.json
│   └── supersession.json
├── policies/               # User-managed configuration
├── runs/ingestion/         # Execution logs
└── archive/                # Archived assets
```

## Package Structure (per document)

```
{doc_id}/
├── manifest.yaml           # Document metadata
├── normalized/
│   ├── clean.md            # Markdown-formatted text
│   └── plain.txt           # Plain text
├── structure/
│   ├── outline.json        # Section hierarchy
│   ├── defined_terms.json  # Defined terms list
│   ├── crossrefs.json      # Cross-references
│   └── exhibits.json       # Exhibits and annexes
├── clauses/
│   ├── clause-001.json
│   ├── clause-002.json
│   └── ...
└── quality/
    ├── validation-report.json
    └── review-flags.json
```

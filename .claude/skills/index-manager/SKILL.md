# index-manager Skill

Manage library indexes for document and clause retrieval.

## Capabilities

1. **Index Build / Rebuild** (`scripts/build-index.py`)
   - Scans `approved/` directory and rebuilds all indexes
   - Usage: `python3 build-index.py rebuild`
   - Or register a single document: `python3 build-index.py register <manifest_path>`
   - Rebuilds: `documents.json`, `clauses.json`, `terms.json`, `retrieval-map.json`, `supersession.json`

2. **Index Query** (`scripts/query-index.py`)
   - 2-stage deterministic filtering for review candidate retrieval
   - Stage 1: filter by contract_family, jurisdiction, governing_law, approval_state, status
   - Stage 1.5: narrow by clause_type when Stage 1 > 50 candidates
   - Stage 2: exclude archived, superseded, quarantined records
   - Freshness rules: downrank or exclude stale records
   - Ranking honors `retrieval-priority.yaml` priority buckets, language preference, and affinity-family expansion
   - Usage: `python3 query-index.py query '{"contract_family":"nda"}'`
   - Search: `python3 query-index.py search '{"query_text":"liability","clause_type":"limitation_of_liability"}'`
   - Redline patterns: `python3 query-index.py redline-patterns '{"contract_family":"safe","clause_type":"indemnification"}'`

3. **Coverage Reporting** (`scripts/report-coverage.py`)
   - Summarizes configured family coverage, observed clause types, unmapped ratios, and top unmapped headings
   - Usage: `python3 report-coverage.py`

4. **Supersession Management** (`scripts/supersession.py`)
   - Mark documents as superseded: `python3 supersession.py supersede <old_id> <new_id>`
   - View chain: `python3 supersession.py chain <doc_id>`

## When to Use

- After approval gate (WF1 Step 10): register new document
- During review retrieval (WF2 Step 5): query candidates
- During taxonomy / library audits: generate a coverage report
- Library management commands: list, search, rebuild
- When superseding documents

## Index Files

| File | Content | Location |
|------|---------|----------|
| `documents.json` | All approved document metadata | `library/indexes/` |
| `clauses.json` | All clause records from approved docs | `library/indexes/` |
| `terms.json` | All defined terms | `library/indexes/` |
| `retrieval-map.json` | Clause lookup by family:type key | `library/indexes/` |
| `supersession.json` | Supersession chains | `library/indexes/` |
| `redline-patterns.json` | Past review patterns by family:clause_type | `library/indexes/` |
| `negotiation-history.json` | Multi-round negotiation history by deal_id | `library/indexes/` |

## Query Pipeline for Review (Step 5)

When performing library candidate retrieval for a review:

1. Call `query-index.py query` with the target's `contract_family`, optional `jurisdiction` and `governing_law`
2. Pass `target_clauses` as a list of `{clause_type}` dicts for per-clause narrowing
3. Optionally pass `language` to soft-prefer same-language candidates without excluding null-language records
4. If exact-family coverage is thin, query expansion can include configured affinity families with a ranking penalty
5. If `library_empty` is true, or `general_review_mode` is true, or `total_candidates == 0`, proceed in **general review mode**
6. Pass filtered candidates to LLM for semantic matching (Stage 3)

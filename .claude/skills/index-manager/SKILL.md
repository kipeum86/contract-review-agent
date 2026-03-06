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
   - Usage: `python3 query-index.py query '{"contract_family":"nda"}'`
   - Search: `python3 query-index.py search '{"query_text":"liability","clause_type":"limitation_of_liability"}'`

3. **Supersession Management** (`scripts/supersession.py`)
   - Mark documents as superseded: `python3 supersession.py supersede <old_id> <new_id>`
   - View chain: `python3 supersession.py chain <doc_id>`

## When to Use

- After approval gate (WF1 Step 10): register new document
- During review retrieval (WF2 Step 5): query candidates
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

## Query Pipeline for Review (Step 5)

When performing library candidate retrieval for a review:

1. Call `query-index.py query` with the target's `contract_family`, optional `jurisdiction` and `governing_law`
2. Pass `target_clauses` as a list of `{clause_type}` dicts for per-clause narrowing
3. If `library_empty` is true in the response, proceed in **general review mode**
4. Pass filtered candidates to LLM for semantic matching (Stage 3)

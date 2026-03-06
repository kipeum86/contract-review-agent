# Library Management

You are managing the contract review library. Execute the requested library operation.

$ARGUMENTS

---

## Available Commands

If no specific command is given, ask the user what they'd like to do.

### list

List assets in the library. Read `contract-review/library/indexes/documents.json` and display a summary table:
- doc_id, title, doc_class, contract_family, status, approval_state
- Support filtering by: doc_class, contract_family, status

### show [doc_id]

Display full details of a specific asset:
- Manifest metadata
- Clause count and clause types
- Validation report summary
- Related playbooks/comment banks

### search [query]

Search the library by structured criteria and/or natural language:
1. Filter `contract-review/library/indexes/clauses.json` by clause_type, contract_family, jurisdiction
2. For semantic queries, use LLM judgment to match against clause text

### deprecate [doc_id]

Set the asset's `status` to `deprecated`. Refresh indexes. Confirm with the user before executing.

### archive [doc_id]

Move the asset from `approved/` to archive status. Exclude from active indexes. Confirm with the user before executing.

### supersede [old_doc_id] [new_doc_id]

Register a new asset as the successor of an old one. Update the supersession chain. Requires user confirmation.

### refresh [doc_id]

Update the `last_legal_refresh_date` field. Clear stale status. Requires user confirmation.

### rebuild-index

Perform a full scan of `contract-review/library/approved/` and regenerate all index files in `contract-review/library/indexes/`. Use this to recover from index corruption.

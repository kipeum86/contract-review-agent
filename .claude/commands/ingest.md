# Library Ingestion Pipeline

You are ingesting documents into the contract review library. The user has placed source files in `contract-review/library/inbox/raw/`.

$ARGUMENTS

---

## Process

### Step 1: Scan inbox

Scan `contract-review/library/inbox/raw/` for files. Supported formats: DOCX, PDF, MD, TXT, HTML. If no files are found, inform the user and stop.

Check `contract-review/library/inbox/sidecars/` for any matching sidecar metadata files (YAML).

### Step 2: Fingerprint & duplicate check

For each file:
- Generate a SHA-256 content hash
- Assign a provisional `doc_id` (lowercase, hyphenated)
- Compare the hash against existing entries in `contract-review/library/indexes/documents.json`
- If exact duplicate found, skip and log

### Step 3: Normalize

Convert each file to clean Markdown (`clean.md`) and plain text (`plain.txt`):
- DOCX: extract text preserving heading hierarchy, numbering, and table structure
- PDF: extract text (requires pdftotext/pymupdf/pypdf)
- MD/TXT/HTML: normalize formatting

If normalization fails, move the file to `contract-review/library/quarantine/` with an error log.

### Step 4: Classify

Using the normalized text and policy files (`contract-review/library/policies/contract-families.yaml`, `clause-taxonomy.yaml`):
- Determine: `doc_class` (template/precedent/playbook/comment_bank), `contract_family`, `subtype`, `paper_role`, `jurisdiction`, `governing_law`, `language`
- Apply sidecar values first if available, infer only missing fields
- Assign classification confidence (high/medium/low)

If confidence is low, route to `contract-review/library/staging/` for human review.

### Step 5: Structural parse

Identify heading hierarchy, section numbering, defined terms, cross-references, and exhibits/annexes. Output as structured JSON.

### Step 6: Clause segmentation

Segment the document into clause-level units. Assign each clause a `clause_type` from `clause-taxonomy.yaml`. Mark unmapped clauses (do not guess). If unmapped ratio exceeds 30%, flag for human review.

### Step 7: Metadata enrichment

Complete the `manifest.yaml` with all required fields per `metadata-schema.yaml`. Assign `authority_level`, determine `external_safe` eligibility, identify supersession candidates.

### Step 8: Validation

- Schema validation against `metadata-schema.yaml`
- Check for privileged content patterns
- Verify cross-reference integrity
- Hard fail conditions -> quarantine
- Soft fail conditions -> staging for human review

### Step 9: Approval gate

Check `contract-review/library/policies/approval-rules.yaml`:
- **Auto-approval (default for templates/precedents)**: If classification confidence = high and zero soft-fail conditions, approve automatically
- **Human review**: For playbooks, comment banks, or any soft-fail conditions, present a summary and ask for approval

### Step 10: Publish & index

Move approved assets to `contract-review/library/approved/`. Update all index files in `contract-review/library/indexes/`:
- `documents.json`, `clauses.json`, `terms.json`, `retrieval-map.json`, `supersession.json`

Report the result: number of files processed, approved, quarantined, and staged.

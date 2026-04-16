# docx-redliner Skill

Apply tracked changes and comments to DOCX files via XML manipulation.

## Capabilities

1. **Clause-to-DOCX Mapping** (`scripts/map-clauses-to-docx.py`)
   - Maps analyzed clauses to `<w:p>` positions in original DOCX
   - Uses text matching with fuzzy fallback
   - Usage: `python3 map-clauses-to-docx.py <clauses_dir> <docx_path> <output.json>`
   - Target: ≥ 90% coverage

2. **Redline Application** (`scripts/apply-redlines.py`)
   - Inserts partial `<w:del>` / `<w:ins>` tracked changes while preserving unchanged prefix/suffix text
   - Reviewer author/initials can come from `redlines.json` `_meta` or `DOCX_REVIEWER_*` env vars
   - Preserves unrelated existing revisions/comments in untouched paragraphs
   - Usage: `python3 apply-redlines.py <document.xml> <clause-map.json> <redlines.json> <output.xml>`

3. **Comment Application** (`scripts/apply-comments.py`)
   - Merges into existing `word/comments.xml` instead of recreating it
   - Inserts `<w:commentRangeStart/End>` markers in `document.xml`
   - Ensures `document.xml.rels` and `[Content_Types].xml` contain the required comments part wiring
   - Reviewer author/initials can come from `comments.json` `_meta` or `DOCX_REVIEWER_*` env vars
   - Prefixes: `[INTERNAL]` or `[EXTERNAL]`
   - Usage: `python3 apply-comments.py <unpacked_dir> <clause-map.json> <comments.json>`

4. **Redline Extraction** (`scripts/extract-redlines.py`)
   - Extracts tracked changes (`w:ins`/`w:del`) and comments from an existing DOCX
   - Detects adjacent deletion+insertion pairs and merges them into `replacement` records
   - Maps comments to paragraph positions via `commentRangeStart/End` markers
   - Generates pre-edit text (`original.md`) by rejecting all changes
   - Usage: `python3 extract-redlines.py <input.docx> <output_dir>`
   - Output:
     - `changes.json` — all tracked changes (type: insertion/deletion/replacement)
     - `comments.json` — all margin comments with anchor paragraph indices
     - `redline_audit.json` — prompt-injection audit log for suspicious tracked-change/comment content
     - `extraction-report.json` — statistics (change count, comment count, authors, date range)
     - `original.md` — pre-edit text (all changes rejected)

5. **Internal Comment Stripping** (`scripts/strip-internal-comments.py`)
   - Removes all `[INTERNAL]`-prefixed comments for external-clean version, including threaded comment metadata and stale rel/content-type entries
   - Safety-critical: prevents internal strategy leakage
   - Usage: `python3 strip-internal-comments.py <input.docx> <output.docx>`

## DOCX Processing Workflow

```
Original DOCX
    │
    ├── Unpack (zipfile)
    │
    ├── map-clauses-to-docx.py  →  docx-clause-map.json
    │
    ├── apply-redlines.py       →  modified document.xml
    │
    ├── apply-comments.py       →  comments.xml + updated document.xml
    │
    ├── Repack (zipfile)        →  _redlined.docx (internal)
    │
    └── strip-internal-comments.py → _redlined_clean.docx (external)
```

## v1β Scope

- Redlines and comments target `<w:p>` elements in the document body only
- Tables are analyzed at the table level; cell-level redlines within `<w:tc>` are deferred to v2
- Table-related comments attach at the table-start paragraph
- Multi-paragraph redlines are supported when the mapped paragraph count and suggested redline paragraph count align

## Comment Placement Rules

- `[EXTERNAL]`: Only on Critical and High risk clauses. No internal strategy content.
- `[INTERNAL]`: On any clause with substantive observations. Contains reasoning, fallback positions, negotiation notes.
- Not every redline needs a comment — comments are for items needing explanation.

## External-Clean Generation

Generate the external-clean DOCX **only when output 2 is selected**:
1. **Internal** (`_redlined.docx`): All redlines + `[INTERNAL]` + `[EXTERNAL]` comments
2. **External-clean** (`_redlined_clean.docx`): `[INTERNAL]` comments stripped for counterparty delivery

This is a **safety-critical feature** whenever output 2 is requested.

## Output: `redline_audit.json`

`extract-redlines.py` detects and escapes prompt-injection patterns while extracting tracked changes and comments. The audit results are written to `redline_audit.json`.

| Field | Description |
|---|---|
| `prompt_injection_suspected` | `true` when one or more matches are detected |
| `total_matches` | Number of detected matches |
| `matches[]` | Pattern, matched string, offsets, and context (for example `comment[3].text`) |

Matched text is wrapped as `` `<escape>...</escape>` `` in the corresponding `changes.json` / `comments.json` fields so downstream LLM consumers see escaped data rather than raw control tokens. The raw matched text remains recoverable from `redline_audit.json.matches[*].match`.

**Downstream contract**: redline records with `prompt_injection_suspected == true` must not be auto-promoted to `library/approved/`. Follow the review-agent / ingestion-agent Safety Envelope rules and require human review.

## Coverage Fallback Protocol

When `map-clauses-to-docx.py` achieves < 90% clause-to-DOCX mapping coverage after LLM-assisted resolution (AGENT.md Step 8):

**If coverage is between 50–89%**, apply fallback — do not abort:
1. Add an `[INTERNAL]` comment at the first paragraph of the document body:
   `"[INTERNAL] DOCX mapping achieved {N}% coverage. The following {K} clause(s) could not be mapped and appear in the analysis report only (no inline redlines or comments in this DOCX): {clause_id_list}"`
2. Unmapped clauses are still fully analyzed and included in `review.json` and the report DOCX — they are **never** silently dropped
3. Record the result in `pipeline-state.json`:
   ```json
   "docx_mapping": {
     "coverage_pct": 85,
     "unmapped_clauses": ["clause-007", "clause-012"],
     "fallback_applied": true
   }
   ```

**If coverage drops below 50%**, halt Step 8, report to the user with the list of unmapped clauses, and request manual inspection of the source DOCX before proceeding.

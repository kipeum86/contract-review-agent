# clause-segmenter Skill

Segment contract documents into clause-level units and classify each clause.

## When to Use

After structural parse (Step 5), at the clause segmentation step (Step 6) of both ingestion and review pipelines.

## Segmentation Process

You perform clause segmentation as an LLM judgment task. Follow these rules:

### Input
- `clean.md` — the normalized document text
- `structure/outline.json` — the structural parse result with section hierarchy
- `clause-taxonomy.yaml` — the classification taxonomy (from `library/policies/`)

### Segmentation Rules

1. **One clause per logical unit**: Each substantive section or subsection of the document becomes one clause record. A single numbered section may produce multiple clauses if it contains distinct provisions.

2. **Clause type assignment**: Assign each clause a `clause_type` from `clause-taxonomy.yaml`. Use the taxonomy's category and clause_type IDs exactly. If a clause does not fit any taxonomy entry confidently, assign `unmapped`. **Never guess** — unmapped is better than wrong.

3. **Preserve original text**: The `text` field must contain the exact source text of the clause. Do not paraphrase, summarize, or modify.

4. **Extract cross-references**: For each clause, identify references to other sections (e.g., "as defined in Section 5.1", "subject to Clause 3") and record them in `cross_refs`.

5. **Extract defined terms**: List any defined terms used within the clause in `defined_terms_used`.

### Output Format

For each clause, produce a JSON file named `clause-{NNN}.json`:

```json
{
  "clause_id": "clause-001",
  "section_no": "1.1",
  "heading": "Definitions",
  "clause_type": "definitions",
  "text": "...(full clause text)...",
  "defined_terms_used": ["Agreement", "Confidential Information"],
  "cross_refs": ["Section 5.1", "Exhibit A"],
  "paragraph_count": 3
}
```

### Quality Thresholds

- Total clause count must be ≥ 5 for a valid contract
- Unmapped ratio must be < 30%
- Every substantive section from the outline must appear in at least one clause
- If thresholds are not met, retry once with adjusted segmentation before routing to STAGING

### Guidelines Reference

See `references/segmentation-guide.md` for detailed segmentation examples and edge cases.

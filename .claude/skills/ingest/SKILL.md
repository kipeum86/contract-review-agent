---
name: ingest
description: >
  Processes external reference source files (PDF, DOCX, etc.) dropped into
  library/inbox/ in one step: Markdown conversion, frontmatter generation,
  folder placement, and index update. Triggered by /ingest.
---

# Source Ingest

Drop a reference source file into `contract-review/library/inbox/` and run `/ingest` to process it automatically.

> **Note**: this skill converts and structures **reference sources** — statutes, court decisions, commentary, sample forms. Contract templates and precedents go through the existing 10-step pipeline (ingestion-agent) instead.

## Trigger

- `/ingest` — process the whole inbox
- A natural-language request to add a source, ingest material, or process the inbox

---

## Workflow

```
File dropped into library/inbox/
  │
  ├─ Step 1: Scan files
  ├─ Step 2: Convert to Markdown
  ├─ Step 3: Generate frontmatter + place under sources/
  └─ Step 4: Update indexes
```

Executable implementation:

```bash
python3 .claude/skills/ingest/scripts/source_ingest.py <source-file> \
  --source-id <id> \
  --jurisdiction KR \
  --source-type statute \
  --authority-level primary_law

python3 .claude/skills/ingest/scripts/validate_source_registry.py \
  contract-review/library/sources/source-registry.json
```

### Step 1: Scan the inbox

```
Glob every file under inbox/ (including inbox/raw/)
Supported: .pdf, .docx, .pptx, .xlsx, .html, .md, .txt
Unsupported: .hwp, .hwpx → tell the user to convert to PDF/DOCX and drop it again
```

- If there are no files, report that the inbox is empty and stop
- Recurse into subfolders
- Skip `.gitkeep` and anything under `_processed/`, `_failed/`, `sidecars/`

**Telling contract templates from reference sources:**
- If the user explicitly calls it a source or reference material, handle it here
- If the user calls it a template or a contract to register, route to the ingestion-agent
- If it is unclear, ask:
  > Is this a reference source (statute / court decision / commentary), or a contract template?

### Step 2: Convert to Markdown

| Input format | Conversion |
|--------------|------------|
| `.pdf` | `mcp__markitdown__convert_to_markdown` (uri: `file:///absolute/path`) |
| `.docx` | `mcp__markitdown__convert_to_markdown` |
| `.pptx`, `.xlsx`, `.html` | `mcp__markitdown__convert_to_markdown` |
| `.md`, `.txt` | No conversion needed — use as is |

**On conversion failure:** move the file to `library/inbox/_failed/` and tell the user why.

### Step 3: Generate frontmatter + place under sources/

Generate YAML frontmatter on the converted `.md` file.

```yaml
---
# === Identity ===
source_id: "{category}-{slug}"        # e.g. "statute-commercial-code-capital-increase"
slug: "{generated}"
title_kr: "{title extracted from the document}"
title_en: "{English title if present, otherwise empty}"
document_type: "{statute | enforcement_decree | regulation | guideline | decision | precedent | newsletter | commentary | article | paper | sample_form | other}"

# === Provenance ===
publisher: "{issuing body / firm / journal}"
author: "{author, if extractable}"
published_date: "{publication date, if extractable}"
source_url: "{URL, if extractable}"
original_format: "{pdf | docx | ...}"
ingested_at: "{processing time, ISO 8601}"

# === Search metadata ===
keywords: ["{5-10 content-derived keywords}"]
topics: ["{topic classification}"]
relevant_statutes: ["{cited provisions}"]
contract_families_relevant: ["{related contract types: ssa, sha, safe, spa, license, ...}"]
char_count: {character count}
---
```

**Field extraction logic:**
1. **Title**: the first `#` heading, or bold text at the very top of the document
2. **Keywords**: contract-law terms of art appearing in the document
3. **relevant_statutes**: regex-extract article references and match them to the statute name plus article number
4. **contract_families_relevant**: infer related contract types from the content (see `contract-families.yaml`)
5. **publisher**: firm, institution, or journal name
6. **published_date**: extract date patterns

**Location:** `library/sources/{slug}.md`
- The slug is derived from the title: keep the original script, spaces become hyphens, special characters are dropped
- On collision, append `-2`, `-3`

**Original file:** moved to `library/inbox/_processed/` (never deleted)

### Step 4: Update the indexes

After processing, update `library/sources/source-registry.json`.

**Registry entry structure:**

```json
{
  "source_id": "statute-commercial-code-capital-increase",
  "title_kr": "상법 제418조 (신주의 발행)",
  "document_type": "statute",
  "path": "sources/commercial-code-capital-increase.md",
  "contract_families_relevant": ["ssa", "spa"],
  "keywords": ["신주발행", "주주배정", "제3자배정"],
  "ingested_at": "2026-03-25T10:00:00+09:00"
}
```

`title_kr` and `keywords` hold the source's own wording, so they carry whatever language the source is written in.

If `source-registry.json` does not exist yet, create it.

Validation rules:

- Duplicate `source_id` is a hard failure.
- Missing source file path or SHA mismatch is a hard failure.
- Stale `last_checked` is a warning in `validate_source_registry.py` and must be surfaced in review metadata when cited.
- Review report internal metadata should preserve cited `source_id` values so stale-source warnings can be traced.

---

## Result report

After processing every file, print a summary:

```
Ingest complete

Processed: N files
  Succeeded: X (filename → sources/)
  Failed: Y (moved to _failed/)

Originals moved to library/inbox/_processed/
```

---

## Error handling

| Situation | Response |
|-----------|----------|
| Inbox empty | Report that the inbox is empty |
| Unsupported format (.hwp etc.) | Skip the file and ask for a PDF/DOCX conversion |
| markitdown conversion failed | Move to `_failed/` and report the reason |
| Filename collision | Append `-2`, `-3` to the slug |
| Frontmatter extraction failed | Generate empty values and recommend user review |

---

## Cautions

1. **Preserve originals**: never delete an inbox original — move it to `_processed/`
2. **Large files**: warn and ask for confirmation above 50MB
3. **Scanned PDFs**: recommend user review when OCR quality is poor
4. **Do not clobber**: never overwrite an existing `library/sources/` file with the same slug
5. **Templates are different**: contract templates, as opposed to reference sources, route to the 10-step pipeline

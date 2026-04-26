# doc-parser Skill

Parse and normalize contract documents from various formats into standardized outputs.

## Capabilities

1. **Format Detection** (`scripts/detect-format.py`)
   - Validates file format (DOCX, PDF, MD, TXT, HTML)
   - Checks file integrity via magic bytes
   - Rejects legacy `.doc` binaries with explicit `.docx` conversion guidance
   - Usage: `python3 detect-format.py <file_path>`

2. **Fingerprinting** (`scripts/fingerprint.py`)
   - Computes SHA-256 hash
   - Generates provisional `doc_id`
   - Checks for duplicates against `documents.json`
   - Usage: `python3 fingerprint.py <file_path>`
   - Exit code 2 = exact duplicate found

3. **Normalization** (`scripts/normalize.py`)
   - Converts any supported format to wrapped `clean.md` + raw `plain.txt`
   - DOCX: parses document.xml preserving headings, lists, tables
   - PDF: uses pdftotext → pymupdf → pypdf fallback chain
   - Flags likely image-only/scanned PDFs as `needs_ocr: true` instead of silently failing
   - Wraps `clean.md` in `<untrusted_contract_content source="..."> ... </untrusted_contract_content>`
   - Validates wrapper with `python3 normalize.py --validate-wrapper <clean.md>`
   - Validates output quality (text length ratio check)
   - Usage: `python3 normalize.py <file_path> <output_dir>`

## When to Use

- At the start of any ingestion pipeline (WF1 Steps 1-3)
- At the start of any review pipeline (WF2 Steps 1-2)
- When a new document enters the system

## Output Artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| Format detection result | stdout (JSON) | File format, size, support status |
| Fingerprint result | stdout (JSON) | doc_id, sha256, duplicate status |
| `clean.md` | `{output_dir}/clean.md` | Markdown-formatted normalized text inside the untrusted-content wrapper |
| `plain.txt` | `{output_dir}/plain.txt` | Plain text without formatting |

## Quality Checks

- Normalization validates that output text length is ≥ 50% of source (10% for binary formats)
- Heading count is tracked for structural integrity comparison
- Review/ingestion agents must reject wrapperless `clean.md` artifacts
- Empty files are rejected at detection stage
- Legacy `.doc` files must be converted to `.docx` before normalization
- Scanned PDFs are reported as OCR-required when no extractable text is detected

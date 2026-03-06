# docx-redliner Skill

Apply tracked changes and comments to DOCX files via XML manipulation.

## Capabilities

1. **Clause-to-DOCX Mapping** (`scripts/map-clauses-to-docx.py`)
   - Maps analyzed clauses to `<w:p>` positions in original DOCX
   - Uses text matching with fuzzy fallback
   - Usage: `python3 map-clauses-to-docx.py <clauses_dir> <docx_path> <output.json>`
   - Target: ≥ 90% coverage

2. **Redline Application** (`scripts/apply-redlines.py`)
   - Inserts `<w:del>` and `<w:ins>` tracked change XML
   - Author: "Claude"
   - Preserves original `<w:rPr>` formatting
   - Usage: `python3 apply-redlines.py <document.xml> <clause-map.json> <redlines.json> <output.xml>`

3. **Comment Application** (`scripts/apply-comments.py`)
   - Creates `word/comments.xml` entries
   - Inserts `<w:commentRangeStart/End>` markers in `document.xml`
   - Prefixes: `[INTERNAL]` or `[EXTERNAL]`
   - Usage: `python3 apply-comments.py <unpacked_dir> <clause-map.json> <comments.json>`

4. **Internal Comment Stripping** (`scripts/strip-internal-comments.py`)
   - Removes all `[INTERNAL]`-prefixed comments for external-clean version
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

## Comment Placement Rules

- `[EXTERNAL]`: Only on Critical and High risk clauses. No internal strategy content.
- `[INTERNAL]`: On any clause with substantive observations. Contains reasoning, fallback positions, negotiation notes.
- Not every redline needs a comment — comments are for items needing explanation.

## External-Clean Generation

Both DOCX versions are **always** generated automatically:
1. **Internal** (`_redlined.docx`): All redlines + `[INTERNAL]` + `[EXTERNAL]` comments
2. **External-clean** (`_redlined_clean.docx`): `[INTERNAL]` comments stripped

This is a **safety-critical feature**, not optional.

# Export External-Clean DOCX

Strip all `[INTERNAL]`-prefixed comments from a redlined DOCX to produce a version safe for counterparty delivery.

$ARGUMENTS

---

## Process

1. **Locate the file**: If no file is specified, scan `output/` for redlined DOCX files and ask the user which one to process. If only one exists, use it.

2. **Strip internal comments**:
   - Unpack the DOCX into raw XML
   - Remove all comment entries whose text starts with `[INTERNAL]`
   - Remove corresponding `<w:commentRangeStart>` and `<w:commentRangeEnd>` markers from `document.xml`
   - Preserve all tracked changes and `[EXTERNAL]` comments

3. **Repack**: Reassemble the DOCX and save as `{original_name}_clean.docx` in `output/`.

4. **Verify**: Confirm the output file is valid and report the number of internal comments stripped.

**This is a safety-critical operation** — the output file must contain zero internal strategy, fallback positions, or negotiation leverage information.

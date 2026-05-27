# Export External-Clean DOCX

Strip all `[INTERNAL]`-prefixed comments from a redlined DOCX to produce a version safe for counterparty delivery.

$ARGUMENTS

---

## Process

1. **Locate the file**: Source `.claude/scripts/workspace-paths.sh`. If no file is specified, scan `$CRA_OUTPUT_DIR` first and then any distinct legacy path in `$CRA_OUTPUT_DIRS` for redlined DOCX files. Ask the user which one to process if multiple files exist. If only one exists, use it.

2. **Strip internal comments**:
   - Unpack the DOCX into raw XML
   - Remove all comment entries whose text starts with `[INTERNAL]`
   - Remove corresponding markers from `document.xml`, headers, footers, and related threaded-comment metadata parts
   - Preserve all tracked changes and `[EXTERNAL]` comments

3. **Repack + scan**: Reassemble the DOCX and run `scan-docx-for-internal-markers.py` using `.claude/policies/external-clean-policy.yaml`.

4. **Verify**: If the scanner reports any violation, delete/do not deliver the external-clean DOCX and report the part name plus snippet. Otherwise save as `{original_name}_clean.docx` beside the selected source file and report the number of internal comments stripped.

**This is a safety-critical operation** — the output file must contain zero internal strategy, fallback positions, or negotiation leverage information.

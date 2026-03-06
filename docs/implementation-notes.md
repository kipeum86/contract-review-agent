# Implementation Notes

## Current Phase: v1α

### Implemented Components

#### Foundation
- Full folder structure per design doc §3.1
- 6 policy YAML files with sensible defaults
- 5 empty index JSON files
- CLAUDE.md orchestrator (concise, per §3.2)

#### Scripts (13 total)
| Script | Language | Purpose |
|--------|----------|---------|
| `detect-format.py` | Python | File format detection and validation |
| `fingerprint.py` | Python | SHA-256 hashing and duplicate detection |
| `normalize.py` | Python | DOCX/PDF/MD/TXT/HTML → clean.md + plain.txt |
| `build-index.py` | Python | Index build and rebuild from approved/ |
| `query-index.py` | Python | 2-stage deterministic filtering for retrieval |
| `supersession.py` | Python | Supersession chain management |
| `validate-manifest.py` | Python | Manifest schema validation |
| `validate-package.py` | Python | Package integrity checks |
| `check-privilege-leak.py` | Python | Privileged content pattern detection |
| `save-state.py` | Python | Pipeline state persistence |
| `load-state.py` | Python | State loading and resume detection |
| `diff-rounds.py` | Python | Clause-level diff between rounds |
| `map-clauses-to-docx.py` | Python | MD clause → DOCX paragraph mapping |
| `apply-redlines.py` | Python | Tracked changes XML insertion |
| `apply-comments.py` | Python | Comment XML insertion |
| `strip-internal-comments.py` | Python | Remove [INTERNAL] comments for external-clean |
| `compile-report.js` | Node.js | Analysis report DOCX generation |
| `compile-delta-report.js` | Node.js | Delta report DOCX generation |

#### Skill Files (7 SKILL.md)
- doc-parser, clause-segmenter, index-manager, metadata-validator
- report-compiler, docx-redliner, pipeline-state, contract-review

#### Agent Files (3 AGENT.md)
- ingestion-agent (WF1)
- review-agent (WF2 + WF4)
- drafting-agent (WF5)

#### Reference Documents (4)
- domain-policy.md, review-guide.md, audience-firewall.md, segmentation-guide.md

#### Configuration
- .claude/settings.json with PreToolUse hook for directory protection

### Dependencies
- Python 3.14+ with PyYAML
- Node.js 24+ with `docx` npm package
- Optional: pdftotext, pymupdf, or pypdf for PDF support
- Optional: pandoc for enhanced DOCX conversion

### How to Test

1. **Ingestion test**: Place a DOCX/MD contract in `contract-review/library/inbox/raw/` and run `/ingest`
2. **Review test**: Place a contract to review and run `/review`
3. **Library test**: Run `/library list` or `/library search`

### Known Limitations (v1α)
- PDF extraction requires external tools (pdftotext/pymupdf/pypdf)
- DOCX normalization uses basic XML parsing (no pandoc)
- Report output is JSON+MD only (DOCX reports are v1β)
- No DOCX redlining yet (v1β)

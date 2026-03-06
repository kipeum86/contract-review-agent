# Contract Review Agent — Implementation Design Document

> **Document purpose**: Target architecture and implementation roadmap for building a Contract Review Agent in Claude Code  
> **Status**: Draft v3.0  
> **Date**: 2026-03-06  
> **Related document**: `/.claude/skills/contract-review/references/domain-policy.md` (Folder Schema & Ingestion Policy Reference)
>
> **Changelog (v3.0)**: Phased implementation (v1α → v1β → v2). External-clean DOCX auto-generation promoted to v1β (safety-critical). CLAUDE.md slimmed — detailed rules moved to AGENT.md/SKILL.md. Hooks integration added (§3.17). Explicit slash-command entry points added (§3.16). DOCX redline scoped to body paragraphs in v1β (table cell-level → v2). Validation philosophy clarified (deterministic-first, LLM-secondary).
>
> **Changelog (v2.0)**: DOCX redline/comment direct application promoted to v1. Re-review (delta analysis) added to v1. Pipeline state persistence for resume support. Review mode settings (strict/moderate/loose). Playbook auto-suggestion during ingestion. Negotiation round management. Language-adaptive output. Contract drafting pipeline (Workflow 5) added.

---

## 1. Task Context

### 1.1 Background

Contract review is a repetitive yet precision-critical legal operation. A reviewer receives a counterparty draft, compares it clause-by-clause against the organization's standard positions, assesses acceptability, and produces redline suggestions and explanatory comments. Throughout this process, the reviewer repeatedly references house templates, playbooks, executed precedents, and comment banks.

This agent automates the bulk of that process while preserving a **human-in-the-loop** structure: the agent proposes; the human decides.

### 1.2 Purpose

- Review counterparty paper clause-by-clause against a user's own library of contracting knowledge.
- Produce per-clause risk assessments, redline suggestions, and both external and internal comments.
- Systematically accumulate and manage reusable contracting assets (templates, playbooks, precedents, comment banks).
- Operate as a **versatile, industry-agnostic system** that each user customizes by uploading their own contract assets and editing policy configuration files.
- Run entirely within a Claude Code terminal environment.

### 1.3 Input and Output Definitions

#### Inputs

| Input | Format | Required | Description |
|-------|--------|----------|-------------|
| Target contract | DOCX, PDF, MD, TXT | Yes (review/re-review) | Counterparty or internal draft under review |
| Library assets | DOCX, MD, YAML, JSON | No (cumulative) | House templates, playbooks, comment banks, precedents |
| Sidecar metadata | YAML | No | Auxiliary metadata to assist document classification |
| Matter context | Inline prompt or YAML | No | Deal-specific context, priorities, or constraints |
| Drafting request | Natural language | Yes (drafting) | Contract type, parties, terms — detailed instructions or minimal prompt triggering interview |

#### Outputs

| Output | Format | Description |
|--------|--------|-------------|
| Redlined contract (internal) | DOCX | Original contract with tracked changes and all comments ([INTERNAL] + [EXTERNAL]) |
| Redlined contract (external-clean) | DOCX | Same as internal but with all [INTERNAL] comments automatically stripped — safe for counterparty delivery |
| Draft contract | DOCX | Newly generated contract, signing-ready, with professional formatting |
| Analysis report | DOCX | Separate report document containing Executive Summary (1 page) + full per-clause analysis, risk grades, and recommendations |
| Delta report | DOCX | For re-reviews: changes-only report comparing current round to previous round |
| Self-review report | JSON | Automated risk check results for drafted contracts |
| Review data | JSON | Machine-readable per-clause analysis results for pipeline state and re-review reference |
| Ingestion report | JSON | Library asset registration result |
| Updated indexes | JSON | Refreshed retrieval indexes |

### 1.4 Key Constraints

| Constraint | Detail |
|------------|--------|
| Runtime | Claude Code (terminal), single-user local execution |
| No embedding or vector database | Semantic search is replaced by LLM-judged matching over deterministically filtered candidates |
| DOCX redline via XML manipulation | Tracked changes and comments are applied by unpacking DOCX, editing raw XML, and repacking. Not via python-docx's high-level API (which does not support tracked changes). |
| Final authority rests with the human | The agent recommends; the human approves and dispatches |
| No multi-tenancy | Single user, single library, local filesystem |
| Natural language + slash commands | User issues commands via natural language or explicit slash commands (`/ingest`, `/review`, etc.); slash commands provide stable entry points, natural language routing operates on top |
| Pipeline resumability | All pipeline state is persisted to disk; interrupted pipelines can resume from the last completed step |

### 1.5 Glossary

| Term | Definition |
|------|------------|
| **house position** | The user's preferred contractual stance, as defined in templates and playbooks |
| **counterparty paper** | A contract draft supplied by the opposing party |
| **playbook** | A policy file defining preferred, acceptable, fallback, and prohibited positions for a given clause type |
| **fallback ladder** | An ordered sequence of progressively concessive alternative clauses for use during negotiation |
| **clause-bank** | A materialized store of clause-level records extracted from approved library assets |
| **matter** | A discrete deal or transaction, structurally separated from the reusable library |
| **ingestion** | The process of normalizing, classifying, validating, and publishing a raw document as a controlled library asset |
| **sidecar** | An auxiliary metadata file supplied alongside a source document to assist classification |
| **external_safe** | A boolean flag indicating whether content may be surfaced in counterparty-facing output |
| **review mode** | A global setting (strict / moderate / loose) that controls both the scope of flagged clauses and the acceptable deviation range from house position |
| **round** | A single iteration of contract exchange in a negotiation; each round produces a distinct version of the contract stored in `round_N/` |
| **delta report** | A re-review deliverable that highlights only the changes between the current round and the previous round |
| **pipeline state** | A JSON file recording the last completed step of a pipeline run, enabling resume after interruption |

---

## 2. Workflow Definitions

The system comprises five independent workflows, all coordinated by a single orchestrator.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Orchestrator (CLAUDE.md)                                │
│                                                                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │ Workflow 1  │ │ Workflow 2  │ │ Workflow 3  │ │ Workflow 4  │ │ Workflow 5   │  │
│  │ Library     │ │ Contract    │ │ Library     │ │ Contract    │ │ Contract     │  │
│  │ Ingestion   │ │ Review      │ │ Management  │ │ Re-review   │ │ Drafting     │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2.1 Workflow 1: Library Ingestion Pipeline

**Purpose**: Validate, classify, and structure user-supplied documents into controlled library assets.

**Trigger**: User places a file in `inbox/raw` and issues an ingestion command.

```
User places file in inbox/raw
        │
        ▼
[Step 1] File detection & registration ────────── Script
        │
        ▼
[Step 2] Fingerprinting & duplicate check ─────── Script
        │
        ├── Exact hash match → STOP (log duplicate)
        │
        ▼
[Step 3] Normalization (DOCX/PDF → MD/TXT) ────── Script
        │
        ├── Normalization failure → QUARANTINE
        │
        ▼
[Step 4] Classification & routing ─────────────── LLM judgment
        │
        ├── Live matter document → Route to matters/
        ├── Low classification confidence → STAGING (human review)
        │
        ▼
[Step 5] Structural parse ─────────────────────── LLM judgment + Script
        │
        ▼
[Step 6] Clause segmentation ──────────────────── LLM judgment
        │
        ▼
[Step 7] Metadata enrichment ──────────────────── LLM judgment
        │
        ▼
[Step 8] Validation & risk check ──────────────── Script (schema) + LLM (quality)
        │
        ├── Hard fail → QUARANTINE
        ├── Soft fail → STAGING (human review)
        │
        ▼
[Step 9] Approval gate ────────────────────────── Human review
        │
        ├── Reject → QUARANTINE
        ├── Reference-only → approved/precedents/reference-only
        │
        ▼
[Step 10] Publish & index build ───────────────── Script
        │
        ▼
Asset registered in library
```

#### Step-by-Step Specification

##### Step 1 — File Detection & Registration

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Files in `inbox/raw` |
| **Actions** | Verify supported file format (DOCX, MD, HTML, TXT, PDF). Check for a matching sidecar in `inbox/sidecars`. Create an ingestion run folder at `/library/runs/ingestion/{timestamp}_{doc_id}`. |
| **Output** | Initial run record (JSON) |
| **Success criteria** | At least one file of a supported format is detected |
| **Validation method** | Rule-based — file extension check, file size > 0 |
| **On failure** | Unsupported format or empty file → skip + log |

##### Step 2 — Fingerprinting & Duplicate Check

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Raw source file |
| **Actions** | Generate SHA-256 content hash. Assign a provisional `doc_id`. Compare the hash against existing entries in `documents.json`. |
| **Output** | Manifest stub (YAML), duplicate determination |
| **Success criteria** | `doc_id` generated; duplicate check completed |
| **Validation method** | Schema validation — `doc_id` format, `sha256` format |
| **On failure** | Exact duplicate → log and STOP. Near-duplicate → flag and continue |

##### Step 3 — Normalization

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Raw source file |
| **Actions** | Convert DOCX via pandoc or python-docx to Markdown. Extract text from PDF via pdftotext. Preserve numbering, heading hierarchy, and table structure where possible. Produce `clean.md` and `plain.txt`. |
| **Output** | `normalized/clean.md`, `normalized/plain.txt` |
| **Success criteria** | The normalized text preserves the original section structure |
| **Validation method** | Rule-based — output files exist; text length ≥ 50% of original (to detect excessive loss); heading count comparison |
| **On failure** | Text extraction failure or excessive structural loss → QUARANTINE |

##### Step 4 — Classification & Routing

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | `clean.md` + sidecar metadata (if available) + `contract-families.yaml` + `clause-taxonomy.yaml` |
| **Actions** | Determine the following classification axes: `doc_class`, `contract_family`, `subtype`, `paper_role`, `jurisdiction`, `governing_law`, `language`. Where a sidecar is present, apply sidecar values first and infer only the missing fields. Assign a classification confidence score (high / medium / low). |
| **Output** | Classification result (JSON), routing decision |
| **Success criteria** | All required classification axes are populated. Confidence ≥ medium. |
| **Validation method** | LLM self-verification — require at least three reasoning sentences supporting the classification. Schema validation — all required fields present. |
| **On failure** | Confidence = low → STAGING (awaiting human review). Classified as a live matter document → route to `matters/`. |

##### Step 5 — Structural Parse

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** (structure identification) + Script (JSON serialization) |
| **Input** | `clean.md` |
| **Actions** | Identify the heading hierarchy. Extract section numbering. Extract defined terms. Map cross-references. Identify exhibits, annexes, and schedules. |
| **Output** | `structure/outline.json`, `structure/defined_terms.json`, `structure/crossrefs.json`, `structure/exhibits.json` |
| **Success criteria** | `outline.json` contains at least 5 identified sections. At least 1 defined term is extracted (virtually all contracts contain defined terms). |
| **Validation method** | Schema validation — structural soundness of each JSON output. Rule-based — section count is not anomalously low. |
| **On failure** | Automatic retry ×1 (with adjusted prompt). If the retry fails → soft fail, route to STAGING. |

##### Step 6 — Clause Segmentation

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | `clean.md` + `structure/outline.json` + `clause-taxonomy.yaml` |
| **Actions** | Segment the document into clause-level units. Assign each clause a `clause_type` from `clause-taxonomy.yaml`. Mark any clause that cannot be confidently mapped as `unmapped` (guessing is prohibited). For each clause, extract `section_no`, `heading`, `text`, `defined_terms_used`, and `cross_refs`. |
| **Output** | `clauses/clause-001.json`, `clause-002.json`, ... |
| **Success criteria** | Every substantive section of the document is represented by at least one clause record. The unmapped ratio remains below 30%. |
| **Validation method** | Rule-based — clause record count ≥ 5; unmapped ratio check. LLM self-verification — confirm that no sections from the source have been omitted. |
| **On failure** | Excessive unmapped clauses → soft fail, route to STAGING. Anomalous clause count → automatic retry ×1. |

##### Step 7 — Metadata Enrichment

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | Clause records + manifest stub + existing library indexes |
| **Actions** | Assign `authority_level` (preferred / acceptable / fallback / reference_only). Determine `external_safe` eligibility. Mark freshness-sensitive sections. Identify supersession candidates by comparing against existing library assets. Link related playbook and comment-bank entries where available. |
| **Output** | Completed `manifest.yaml`, enriched clause records, `quality/review-flags.json` |
| **Success criteria** | All required fields in `manifest.yaml` are populated |
| **Validation method** | Schema validation — check against `metadata-schema.yaml` required fields |
| **On failure** | Missing fields → automatic retry ×1 (re-request with explicit listing of missing fields) |

##### Step 8 — Validation & Risk Check

| Field | Detail |
|-------|--------|
| **Executor** | Script (schema validation, rule checks) + **LLM judgment** (quality review) |
| **Input** | The complete package |
| **Actions** | **Script**: Validate manifest schema. Check numbering continuity. Verify cross-reference integrity. Re-confirm duplicate hash status. **LLM**: Detect internal comments or privileged content. Assess metadata consistency. Verify that freshness-sensitive clauses carry a `legal_refresh_date`. |
| **Output** | `quality/validation-report.json`, `quality/review-flags.json` |
| **Success criteria** | Zero hard-fail conditions |
| **Validation method** | Rule-based — automatic determination against hard-fail and soft-fail condition lists |
| **On failure** | Hard fail → QUARANTINE. Soft fail → STAGING (awaiting human review). |

**Hard-fail conditions:**
- Normalized text is absent or empty
- Structural parse output is missing
- Three or more required manifest fields are missing
- Privileged content is detected but cannot be isolated
- The source file is corrupt or unreadable

**Soft-fail conditions:**
- Unmapped clauses ≥ 30%
- Defined term extraction failed
- Governing law is ambiguous
- Near-duplicate conflict is unresolved
- A freshness-sensitive clause lacks a `legal_refresh_date`

##### Step 9 — Approval Gate

| Field | Detail |
|-------|--------|
| **Executor** | **Conditional: Auto-approval or Human review** |
| **Input** | Staging package + validation report + review flags + classification confidence |
| **Actions** | **Auto-approval path**: If all of the following are true — (1) zero soft-fail conditions, (2) classification confidence = high, (3) schema validation passed — the agent automatically approves and proceeds to Step 10. **Human review path**: If any condition above is not met, the agent presents a package summary to the human. The human renders an approval decision: approve / reference-only / reject / archive. The auto-approval policy is defined in `approval-rules.yaml` and can be toggled on/off by the user. |
| **Output** | Updated `approval_state` |
| **Success criteria** | An explicit decision exists (auto or human) |
| **Validation method** | Rule-based — confirm the decision value is valid |
| **On failure** | No decision rendered → remain in waiting state |

**Summary items the agent must present to the human:**
1. Document title, classification result, and confidence level
2. Total clause count and unmapped clause count
3. Soft-fail reasons (if any)
4. Supersession candidates (if any)
5. Recommended publication target (template / approved precedent / reference-only / archive)

##### Step 10 — Publish & Index Build

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Approved package |
| **Actions** | Copy the package into the appropriate `approved/` subtree. Materialize clause-bank records. Refresh `documents.json`, `clauses.json`, `terms.json`, `retrieval-map.json`, and `supersession.json`. Update the status of superseded prior assets. |
| **Output** | Published package under `approved/`, refreshed index files |
| **Success criteria** | The new asset appears in indexes. Superseded assets are correctly marked. |
| **Validation method** | Schema validation — index file structural soundness. Rule-based — `doc_id` present in the relevant index. |
| **On failure** | Index build failure → automatic retry ×1. Retry failure → escalation (notify the human). |

---

### 2.2 Workflow 2: Contract Review Pipeline

**Purpose**: Review a counterparty contract clause-by-clause against the user's library and produce a structured review report.

**Trigger**: User designates a target contract and issues a review command.

```
User provides target contract
        │
        ▼
[Step 1] Target document normalization ──────────── Script
        │
        ▼
[Step 2] Target document classification ─────────── LLM judgment
        │
        ▼
[Step 3] Target document structural parse ───────── LLM judgment + Script
        │  (cross-ref map generated here)
        ▼
[Step 4] Target document clause segmentation ────── LLM judgment
        │
        ▼
[Step 5] Library candidate retrieval ────────────── Script (filter) + LLM (matching)
        │
        ├── Library empty → Warning, then general review mode
        │
        ▼
[Step 6] Per-clause comparative analysis ────────── LLM judgment
        │  (review mode: strict/moderate/loose applied here)
        ▼
[Step 7] Comment & redline suggestion generation ── LLM judgment
        │  ([INTERNAL] + [EXTERNAL] comments; audience firewall)
        ▼
[Step 8] MD → DOCX clause mapping ──────────────── Script + LLM
        │
        ▼
[Step 9] DOCX redline & comment application ─────── Script (XML manipulation)
        │
        ▼
[Step 10] Report compilation (DOCX) ─────────────── Script + LLM (summary)
        │
        ▼
[Step 11] Pipeline state save ───────────────────── Script
        │
        ▼
[Step 12] Human review ─────────────────────────── Human review
        │
        ├── Revision requested → Re-run Steps 6–10 for affected clauses only
        │
        ▼
Final review deliverables complete
(Internal Redlined DOCX + External-Clean DOCX + Analysis Report DOCX + Review Data JSON)
```

#### Step-by-Step Specification

##### Steps 1–4 — Target Document Parsing

These steps apply the same logic as Workflow 1, Steps 3–6, with the following differences:

- `doc_class` is fixed to `review_target` (the document is not a library registration candidate).
- Parse outputs are stored under `matters/{matter_id}/round_{N}/working/`.
- No approval gate applies (this is a matter document, not a library asset).
- **Step 3 additionally generates a cross-reference map** (`structure/crossref-map.json`) that resolves all internal references (e.g., "as defined in Section 5.1") to their target section/clause IDs. This map is attached as context to each section when the document is processed in chunks for large documents.
- **For large documents exceeding the context window**: The document is split at section boundaries. Each section chunk receives the cross-ref map and defined terms list as shared context, ensuring that references to other sections are not lost during analysis.

##### Step 5 — Library Candidate Retrieval

| Field | Detail |
|-------|--------|
| **Executor** | Script (deterministic filter) + **LLM judgment** (candidate selection) |
| **Input** | Target document classification + `clauses.json` index + `retrieval-map.json` + `retrieval-priority.yaml` |
| **Actions** | **Stage 1 — Deterministic Filter (Script):** Filter `clauses.json` by `contract_family` match → `jurisdiction` or `governing_law` match → `approval_state = approved` → `status = active`, applied in that order. **Stage 1.5 — Narrowing Filter (Script):** If the Stage 1 result exceeds 50 candidates, apply a secondary filter by `clause_type` match against the target clause's assigned `clause_type`, reducing the candidate set to the most relevant entries per clause. **Stage 2 — Exclusion (Script):** Exclude archived, quarantined, and superseded records (where an active successor exists). Exclude `external_unsafe` records when generating external-facing comments. Exclude or down-rank stale freshness-sensitive records. **Stage 3 — LLM Matching:** Present the filtered candidate list (typically 10–30 clauses) to the LLM. For each target clause, the LLM selects the most appropriate library match, prioritizing `clause_type` alignment first and textual semantic similarity second. |
| **Output** | Per-clause matching result (JSON mapping target `clause_id` → library `clause_id`) |
| **Success criteria** | At least 50% of target document clauses are matched to a library candidate |
| **Validation method** | Rule-based — match rate check. LLM self-verification — at least one reasoning sentence per match. |
| **On failure** | Library empty → warning message, then proceed in general review mode (risk analysis based on general contract law principles, without house position comparison). Match rate < 50% → warning message, then proceed. |

**General review mode (when the library is empty):**
- The LLM performs risk analysis grounded in general contract law principles only.
- The report explicitly states that it was produced under general review mode without library-backed house position comparison.
- House position comparison is omitted entirely.

##### Step 6 — Per-Clause Comparative Analysis

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | Target clause text + matched library clause + relevant playbook + fallback ladder + **review mode setting** |
| **Actions** | For each clause: (1) identify divergences from house position; (2) assign a risk grade (Critical / High / Medium / Low / Acceptable); (3) determine acceptability against the playbook — specifically, which tier the clause falls into: preferred, acceptable, fallback, or prohibited; (4) derive whether modification is necessary and in what direction. **Review mode** controls both analysis scope and tolerance: **strict** = flag all deviations from template, only `preferred` playbook tier is acceptable; **moderate** = flag Critical + High risk items, `acceptable` tier is tolerated; **loose** = flag Critical only, `fallback` tier is tolerated. When a playbook is absent for a given `clause_type`, the agent uses the matched template clause text as the house position baseline and includes a `playbook_missing` warning in the output. |
| **Output** | Per-clause analysis result (JSON) |
| **Success criteria** | Every matched clause has a risk grade and supporting rationale |
| **Validation method** | LLM self-verification — at least two reasoning sentences per judgment. Schema validation — `risk_level` value falls within the permitted enum. |
| **On failure** | Automatic retry ×1 (when rationale is insufficient). On retry failure → mark the clause as "manual review required." |

##### Step 7 — Comment & Redline Suggestion Generation

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | Step 6 analysis results + comment-bank (external / internal) + fallback ladder + review mode setting |
| **Actions** | (1) **External comment** (`[EXTERNAL]` prefix): If a suitable existing comment exists in `comment-bank/external`, adapt and reuse it. Otherwise, generate a new one. **Only materials flagged `external_safe = true` may be referenced.** Comments are generated only for Critical and High risk clauses (or as expanded by review mode). (2) **Internal note** (`[INTERNAL]` prefix): Reference `comment-bank/internal`. Check escalation conditions. Include reasoning, negotiation strategy notes, and fallback positions. Generated for all clauses where a substantive observation exists. (3) **Redline suggestion**: Propose alternative clause text drawing on the fallback ladder. Scope is governed by review mode: strict = all deviations; moderate = Critical + High; loose = Critical only. |
| **Output** | Per-clause `external_comment`, `internal_note`, `suggested_redline` |
| **Success criteria** | Every clause graded Critical or High must have both an `external_comment` and a `suggested_redline` |
| **Validation method** | Rule-based — mandatory field existence check for Critical/High clauses. LLM self-verification — confirm that `external_comment` contains no internal strategy information (audience firewall check). |
| **On failure** | Audience firewall violation detected → delete the offending comment and regenerate (up to 2 retries). **After 2 failed retries → clear the `external_comment` entirely, set it to `"[MANUAL_REQUIRED] Audience firewall could not be satisfied. Manual drafting required."`, and proceed.** |

##### Step 8 — MD → DOCX Clause Mapping

| Field | Detail |
|-------|--------|
| **Executor** | Script + **LLM judgment** (for ambiguous mappings) |
| **Input** | Clause records (from MD-based analysis) + original DOCX (unpacked XML) |
| **Actions** | Map each analyzed clause back to its corresponding position in the original DOCX XML. The script performs text-matching between the normalized clause text and the raw DOCX paragraph text. For ambiguous matches (e.g., repeated boilerplate), the LLM resolves the mapping. Output is a mapping file linking each `clause_id` to specific `<w:p>` element positions in `document.xml`. |
| **Output** | `working/docx-clause-map.json` (clause_id → DOCX paragraph index mapping) |
| **Success criteria** | ≥ 90% of analyzed clauses are mapped to a DOCX position |
| **Validation method** | Rule-based — mapping coverage check |
| **On failure** | Unmapped clauses → log warning, proceed without redline for those clauses, note in report |

##### Step 9 — DOCX Redline & Comment Application

| Field | Detail |
|-------|--------|
| **Executor** | Script (XML manipulation) |
| **Input** | Original DOCX + `docx-clause-map.json` + per-clause redline suggestions + per-clause comments |
| **Actions** | (1) **Unpack** the original DOCX into raw XML using `unpack.py`. (2) For each clause with a `suggested_redline`: locate the target `<w:r>` elements via the clause map, insert `<w:del>` and `<w:ins>` tracked change XML with author="Claude". Preserve original `<w:rPr>` formatting. (3) For each clause with comments: use `comment.py` to create comment entries, then insert `<w:commentRangeStart/End>` markers in `document.xml`. Comments are prefixed with `[INTERNAL]` or `[EXTERNAL]`. (4) **Repack** using `pack.py` with validation. |
| **Output** | Internal redlined DOCX at `output/reports/{matter_id}_round_{N}_redlined.docx` + external-clean DOCX at `output/reports/{matter_id}_round_{N}_redlined_clean.docx` (auto-generated via `strip-internal-comments.py`) |
| **Success criteria** | DOCX opens correctly in Microsoft Word with tracked changes and comments visible |
| **Validation method** | Rule-based — `pack.py` validation passes; file size > 0; XML schema compliance |
| **On failure** | XML validation failure → automatic retry ×1 (regenerate the problematic tracked change block). On retry failure → produce the DOCX without the failing clause's redline and log the omission. |

##### Step 10 — Report Compilation (DOCX)

| Field | Detail |
|-------|--------|
| **Executor** | Script (compilation) + **LLM judgment** (executive summary) |
| **Input** | Full results from Steps 6 and 7 |
| **Actions** | **Script**: Assemble per-clause analysis results into a structured DOCX report using `docx-js`. The report includes: (1) Executive Summary (1 page) — overall risk profile, top 5 key issues, items requiring immediate negotiation attention, and a general recommendation; (2) Full per-clause analysis — risk grade, divergence description, rationale, redline suggestion text, and internal notes for each clause. **LLM**: Generate the Executive Summary narrative. **Language policy**: Redline text in the DOCX follows the contract's original language. The analysis report language follows the user's prompt language, or an explicit language instruction if provided. |
| **Output** | `output/reports/{matter_id}_round_{N}_report.docx`, `output/reports/{matter_id}_round_{N}_review.json` |
| **Success criteria** | The report contains both the executive summary and all per-clause analyses |
| **Validation method** | Schema validation — report structural conformance; DOCX validation passes |
| **On failure** | Compilation failure → automatic retry ×1 |

##### Step 11 — Pipeline State Save

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Completion status of all preceding steps |
| **Actions** | Write a pipeline state file recording the current step, all intermediate artifact paths, and the timestamp. This enables resume from interruption. |
| **Output** | `matters/{matter_id}/round_{N}/pipeline-state.json` |
| **Success criteria** | State file written successfully |
| **Validation method** | Rule-based — file exists and is valid JSON |
| **On failure** | Log warning, proceed (state save failure is non-blocking) |

**Pipeline state file schema:**
```json
{
  "matter_id": "...",
  "round": 1,
  "last_completed_step": 10,
  "step_artifacts": {
    "step_1": {"status": "completed", "output": "working/normalized/clean.md"},
    "step_6": {"status": "completed", "output": "working/analysis/"},
    ...
  },
  "started_at": "...",
  "updated_at": "..."
}
```

##### Step 12 — Human Review

| Field | Detail |
|-------|--------|
| **Executor** | **Human review** |
| **Input** | Redlined DOCX + Analysis Report DOCX |
| **Actions** | The pipeline pauses and presents a summary in the terminal: (1) overall risk profile, (2) count of redlines and comments applied, (3) file paths to all deliverables (internal DOCX, external-clean DOCX, analysis report). The human reviews the output files and may request revisions to specific clause analyses or comments via natural language in the terminal. |
| **Output** | Revision requests (if any) |
| **Success criteria** | The human has acknowledged the report |
| **Validation method** | Human review |
| **On failure** | Revision requested → re-run Steps 6–10 for the affected clauses only, then recompile the full report |

---

### 2.3 Workflow 3: Library Management

**Purpose**: Query, update, and maintain library assets.

**Trigger**: User issues a management command (query / update / archive / delete).

This workflow is not a sequential pipeline but a **command-response pattern**.

| Command | Executor | Action |
|---------|----------|--------|
| `list` — List assets | Script | Read `documents.json`, apply filters, display results |
| `show` — Show asset details | Script | Display the manifest and validation report for a given `doc_id` |
| `search` — Search clauses | Script (filter) + LLM (semantic matching) | Query the clause-bank by structured criteria and, optionally, by meaning |
| `deprecate` — Deactivate an asset | Script | Set `status` to `deprecated`; refresh indexes |
| `archive` — Archive an asset | Script | Move from `approved/` to `archive/`; exclude from indexes |
| `supersede` — Replace an asset | Script + **Human confirmation** | Register a new asset as the successor; update the supersession chain |
| `refresh` — Update freshness | Script + **Human confirmation** | Update `last_legal_refresh_date`; clear stale status |
| `rebuild-index` — Rebuild indexes | Script | Perform a full scan of `approved/` and regenerate all index files |

---

### 2.4 Workflow 4: Contract Re-review Pipeline

**Purpose**: When the counterparty returns a revised version of a previously reviewed contract, analyze the changes against the previous round's results and produce a delta report.

**Trigger**: User designates a revised contract and references an existing matter with a prior round.

```
User provides revised contract + matter_id
        │
        ▼
[Step 1] Round registration ─────────────────────── Script
        │  (create round_{N+1}/ folder, link to prior round)
        ▼
[Step 2] Target document parsing (Steps 1–4) ────── Same as WF2
        │
        ▼
[Step 3] Clause-level diff against prior round ──── Script + LLM judgment
        │
        ├── Classify each clause: unchanged / modified / added / removed
        │
        ▼
[Step 4] Selective re-analysis ──────────────────── LLM judgment
        │  (full re-analysis of all clauses, with prior results as context)
        ▼
[Step 5] Delta report generation ────────────────── Script + LLM
        │
        ▼
[Step 6] DOCX redline & comment application ─────── Script (XML)
        │
        ▼
[Step 7] Human review ──────────────────────────── Human review
        │
        ▼
Delta report + redlined DOCX complete
```

#### Step-by-Step Specification

##### Step 1 — Round Registration

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Revised contract file + `matter_id` |
| **Actions** | Create `round_{N+1}/` folder under `matters/{matter_id}/`. Copy the revised contract into the round folder. Record the link to the prior round (`round_{N}/`) in a `round-meta.json` file. |
| **Output** | `round_{N+1}/round-meta.json` with `prior_round` reference |
| **Success criteria** | Round folder created, prior round reference valid |

##### Step 2 — Target Document Parsing

Same as Workflow 2, Steps 1–4. Outputs stored in `round_{N+1}/working/`.

##### Step 3 — Clause-Level Diff

| Field | Detail |
|-------|--------|
| **Executor** | Script (text diff) + **LLM judgment** (semantic diff for restructured clauses) |
| **Input** | Current round clause records + prior round clause records |
| **Actions** | For each clause in the current version: (1) Script performs text-level matching against prior round clauses by `clause_type` and section position. (2) Classify each clause as `unchanged`, `modified`, `added`, or `removed`. (3) For `modified` clauses, the LLM identifies the substantive nature of the change (narrowing, broadening, clarification, etc.). |
| **Output** | `working/diff-report.json` — per-clause diff classification and change description |
| **Success criteria** | All clauses classified with a diff status |

##### Step 4 — Selective Re-Analysis

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | All current clause records + prior round analysis results + diff report + library matches |
| **Actions** | Re-analyze all clauses (not just changed ones) with the prior round's analysis as additional context. For `unchanged` clauses, the prior analysis is carried forward but re-validated. For `modified`, `added`, and `removed` clauses, full comparative analysis is performed. Each clause's output includes a `delta_summary` field describing what changed compared to the prior round's assessment. |
| **Output** | Per-clause analysis with `delta_summary` and `prior_risk_level` fields |

##### Step 5 — Delta Report Generation

| Field | Detail |
|-------|--------|
| **Executor** | Script + **LLM judgment** (narrative summary) |
| **Input** | Re-analysis results + diff report |
| **Actions** | Generate a delta report (DOCX) focused on changes: (1) Negotiation Progress Summary — which of our prior redline requests were accepted, partially accepted, or rejected; (2) New Issues — clauses that have worsened or newly appeared; (3) Resolved Issues — clauses that have improved or been accepted; (4) Remaining Open Items. |
| **Output** | `output/reports/{matter_id}_round_{N+1}_delta.docx` |

##### Steps 6–7 — DOCX Application & Human Review

Same as Workflow 2, Steps 9 and 12.

---

### 2.5 Workflow 5: Contract Drafting Pipeline

**Purpose**: Generate a new contract from scratch or from a library template, producing a signing-ready DOCX.

**Trigger**: User requests contract drafting (e.g., "NDA 작성해줘", "draft a SaaS agreement").

**Two entry paths:**

- **Path A — Detailed instructions provided**: User supplies comprehensive specifications inline. The agent skips the interview and proceeds directly to drafting.
- **Path B — Minimal instructions**: User provides limited context. The agent conducts a structured interview (max 10 rounds) to gather the necessary information before drafting.

```
User requests contract drafting
        │
        ├── Detailed instructions provided → Skip to Step 3
        │
        ▼
[Step 1] Structured interview ───────────────────── LLM (interactive)
        │  (max 10 rounds, ask all essentials first, follow up on gaps)
        ▼
[Step 2] Interview summary & confirmation ───────── LLM + Human review
        │  (present structured summary, user confirms or corrects)
        ▼
[Step 3] Matter & context registration ──────────── Script
        │
        ▼
[Step 4] Template lookup & clause selection ─────── Script + LLM judgment
        │
        ├── Template found → Customize template clauses
        ├── No template → Generate from scratch
        │
        ▼
[Step 5] Contract generation ────────────────────── LLM judgment
        │
        ▼
[Step 6] Self-review (risk check) ───────────────── LLM judgment
        │  (automated — identify gaps, risks, inconsistencies)
        ▼
[Step 7] DOCX generation ───────────────────────── Script (docx-js)
        │
        ▼
[Step 8] Human review ──────────────────────────── Human review
        │
        ├── Revision requested → Re-run Steps 5–7
        │
        ▼
Signing-ready DOCX complete
(stored in matters/{matter_id}/round_1/)
```

#### Step-by-Step Specification

##### Step 1 — Structured Interview

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** (interactive, multi-turn) |
| **Input** | User's initial request |
| **Actions** | Assess how much information is already provided. If insufficient, conduct an interview to gather: (1) **Business context** — why this contract is needed, the relationship between parties, what's being exchanged; (2) **Parties** — full legal names, roles, jurisdictions; (3) **Core commercial terms** — duration, fees, deliverables, milestones; (4) **Key risk areas** — liability, IP, confidentiality, termination; (5) **Negotiation posture** — leverage level, how aggressive the initial draft should be; (6) **Special requirements** — jurisdiction, governing law, dispute resolution preferences, any unusual provisions. The agent asks all essential questions in the first round, then follows up only on gaps or ambiguities. Maximum 10 interview rounds, but the agent should aim to complete in 2–4 rounds for typical contracts. |
| **Output** | Structured deal context (internal JSON) |
| **Success criteria** | At minimum: contract type, both parties, core commercial terms, and desired language are identified |
| **Validation method** | LLM self-verification — check required fields are populated |
| **On failure** | If critical information is still missing after 10 rounds → proceed with best-effort defaults, flag gaps in the output |

**Interview question categories (priority order):**

| Priority | Category | Example Questions |
|----------|----------|-------------------|
| 1 (Essential) | Contract type & parties | "What type of agreement? Who are the parties?" |
| 2 (Essential) | Business context | "What's the purpose of this deal? What's being exchanged?" |
| 3 (Essential) | Core terms | "Duration? Fee structure? Key deliverables?" |
| 4 (Important) | Risk posture | "What's your negotiation leverage? Aggressive or balanced draft?" |
| 5 (Important) | Legal preferences | "Preferred jurisdiction? Governing law? Dispute resolution?" |
| 6 (If relevant) | Special provisions | "Any unusual terms? Specific concerns?" |

##### Step 2 — Interview Summary & Confirmation

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** + **Human review** |
| **Input** | Structured deal context from Step 1 |
| **Actions** | Present a structured summary of all gathered information to the user in the terminal. Include: parties, contract type, key terms, posture, language, and any assumptions the agent has made. Wait for user confirmation or corrections. |
| **Output** | Confirmed deal context |
| **Success criteria** | User explicitly confirms the summary |
| **On failure** | User provides corrections → update context and re-present summary |

##### Step 3 — Matter & Context Registration

| Field | Detail |
|-------|--------|
| **Executor** | Script |
| **Input** | Confirmed deal context |
| **Actions** | Create a new matter folder (`matters/{matter_id}/`). Write `matter-context.yaml` with the confirmed deal context. Create `round_1/` subfolder for the draft. Set `origin: drafting` in the matter metadata to distinguish from review-originated matters. |
| **Output** | Matter folder structure, `matter-context.yaml` |
| **Success criteria** | Matter folder and context file created |

##### Step 4 — Template Lookup & Clause Selection

| Field | Detail |
|-------|--------|
| **Executor** | Script (index query) + **LLM judgment** (clause tier selection) |
| **Input** | `contract_family` from deal context + library indexes |
| **Actions** | **If template exists**: Query `documents.json` for approved templates matching the `contract_family`. Retrieve the best-match template's clause records. For each clause, select the appropriate tier (preferred / acceptable / fallback) based on the deal's negotiation posture: high leverage → preferred; moderate → preferred with selective acceptable; low leverage → acceptable with selective fallback. **If no template exists**: Flag that the contract will be generated from scratch using general legal knowledge. Log this in the output. |
| **Output** | Selected clause set (JSON) or `template_absent` flag |
| **Success criteria** | Either a clause set is assembled or the absence is acknowledged |
| **Validation method** | Rule-based — clause count check against expected contract structure |

**Clause tier selection matrix:**

| Leverage | Default Tier | Fallback Allowed |
|----------|-------------|------------------|
| High | preferred | No |
| Moderate | preferred (core), acceptable (secondary) | Selective |
| Low | acceptable | Yes |

##### Step 5 — Contract Generation

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | Selected clause set (or scratch mode flag) + deal context + playbooks (if available) + comment bank |
| **Actions** | **Template-based mode**: Customize the selected clauses by filling in deal-specific details (party names, dates, amounts, deliverables). Adjust clause language where the deal context requires deviation from the template. Generate any missing sections (recitals, definitions, signature blocks). **Scratch mode**: Generate the full contract text based on general contract law principles, the deal context, and the specified contract type. Follow standard contract structure for the given type. **For both modes**: Apply the deal-specific language (English or Korean as confirmed). Ensure internal consistency — defined terms are used consistently, cross-references are correct, numbering is continuous. |
| **Output** | Full contract text (structured JSON with section hierarchy) |
| **Success criteria** | Complete contract with all standard sections for the given type |
| **Validation method** | LLM self-verification — check for completeness, consistency, and placeholder elimination |
| **On failure** | Missing sections detected → auto-generate and append. Retry ×1. |

##### Step 6 — Self-Review (Risk Check)

| Field | Detail |
|-------|--------|
| **Executor** | **LLM judgment** |
| **Input** | Generated contract text + deal context + playbooks |
| **Actions** | Perform an automated review of the generated draft, checking for: (1) **Completeness** — all standard sections present for this contract type; (2) **Internal consistency** — defined terms, cross-references, numbering; (3) **Blank fields / placeholders** — no TBD, $____, or unfilled brackets; (4) **Risk assessment** — any provisions that are unusually one-sided even for the selected posture; (5) **Missing protections** — standard clauses that should be present but aren't. Produce a brief self-review report noting any issues found. Auto-fix simple issues (numbering, cross-ref). Flag substantive issues for the user. |
| **Output** | Self-review report (JSON) + corrected contract text |
| **Success criteria** | Zero critical issues remain; all auto-fixable issues resolved |
| **Validation method** | Rule-based — placeholder pattern check. LLM self-verification — completeness and consistency. |
| **On failure** | Critical issues found → auto-fix where possible, flag remainder in the report |

##### Step 7 — DOCX Generation

| Field | Detail |
|-------|--------|
| **Executor** | Script (`docx-js`) |
| **Input** | Final contract text + self-review report |
| **Actions** | Generate a professionally formatted DOCX using `docx-js`. Apply standard legal document formatting: numbered headings, proper margins, signature blocks, page numbers, defined terms in bold on first use. Include any self-review flags as `[INTERNAL]` comments in the DOCX. |
| **Output** | `output/reports/{matter_id}_round_1_draft.docx` + copy in `matters/{matter_id}/round_1/source/` |
| **Success criteria** | DOCX validation passes; professional formatting applied |
| **Validation method** | Rule-based — DOCX validation; file size > 0 |
| **On failure** | Retry ×1 |

##### Step 8 — Human Review

| Field | Detail |
|-------|--------|
| **Executor** | **Human review** |
| **Input** | Draft DOCX + self-review summary |
| **Actions** | Pipeline pauses and presents in the terminal: (1) contract summary (type, parties, key terms); (2) self-review findings (if any); (3) file path. The user reviews the DOCX and may request revisions. |
| **Output** | Revision requests (if any) |
| **Success criteria** | User acknowledges the draft |
| **On failure** | Revision requested → re-run Steps 5–7 with user feedback incorporated |

**Post-drafting lifecycle:**
When the counterparty returns a marked-up version of the drafted contract, the user can initiate a review (Workflow 2) or re-review (Workflow 4) against the same `matter_id`. The draft stored in `round_1/source/` serves as the baseline for comparison.

---

## 3. Implementation Specification

### 3.1 Folder Structure

```
/project-root
├── CLAUDE.md                                    # Main orchestrator instructions
├── /.claude
│   ├── /skills
│   │   ├── /doc-parser                          # Document parsing skill
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── normalize.py                 # DOCX/PDF/MD → clean.md, plain.txt
│   │   │       ├── fingerprint.py               # SHA-256 hash & doc_id generation
│   │   │       └── detect-format.py             # File format detection
│   │   │
│   │   ├── /clause-segmenter                    # Clause segmentation skill
│   │   │   ├── SKILL.md
│   │   │   └── /references
│   │   │       └── segmentation-guide.md        # Segmentation guidelines
│   │   │
│   │   ├── /index-manager                       # Index management skill
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── build-index.py               # Index build and refresh
│   │   │       ├── query-index.py               # Index query (deterministic filter + 2nd stage)
│   │   │       └── supersession.py              # Supersession chain management
│   │   │
│   │   ├── /metadata-validator                  # Metadata validation skill
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── validate-manifest.py         # manifest.yaml schema validation
│   │   │       ├── validate-package.py          # Package integrity checks
│   │   │       └── check-privilege-leak.py      # Privileged content pattern detection
│   │   │
│   │   ├── /report-compiler                     # Report compilation skill
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── compile-report.js            # Analysis results → DOCX report (via docx-js)
│   │   │       └── compile-delta-report.js      # Delta report for re-reviews (via docx-js)
│   │   │
│   │   ├── /docx-redliner                       # DOCX tracked changes & comments skill
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── map-clauses-to-docx.py       # MD clause → DOCX paragraph position mapping
│   │   │       ├── apply-redlines.py            # Insert tracked changes XML into unpacked DOCX
│   │   │       ├── apply-comments.py            # Insert comment XML using comment.py patterns
│   │   │       └── strip-internal-comments.py   # (Utility) Remove [INTERNAL] comments for reference
│   │   │
│   │   ├── /pipeline-state                      # Pipeline state management skill
│   │   │   ├── SKILL.md
│   │   │   └── /scripts
│   │   │       ├── save-state.py                # Write pipeline state JSON
│   │   │       ├── load-state.py                # Read state and determine resume point
│   │   │       └── diff-rounds.py               # Clause-level diff between negotiation rounds
│   │   │
│   │   └── /contract-review                     # Contract review domain knowledge
│   │       ├── SKILL.md
│   │       └── /references
│   │           ├── domain-policy.md             # ← Existing design doc (folder schema & ingestion policy)
│   │           ├── review-guide.md              # Review judgment criteria guide
│   │           └── audience-firewall.md         # External/internal separation rules
│   │
│   └── /agents
│       ├── /ingestion-agent
│       │   └── AGENT.md                         # Ingestion pipeline specialist
│       ├── /review-agent
│       │   └── AGENT.md                         # Contract review + re-review pipeline specialist
│       └── /drafting-agent
│           └── AGENT.md                         # Contract drafting pipeline specialist
│
├── /contract-review
│   ├── /library
│   │   ├── /inbox/raw                           # Source file drop zone
│   │   ├── /inbox/sidecars                      # Auxiliary metadata files
│   │   ├── /staging/{doc_id}/...                # Validated, awaiting approval
│   │   ├── /quarantine/{doc_id}/...             # Failed or rejected
│   │   ├── /approved/...                        # Approved assets (see domain policy for full subtree)
│   │   ├── /indexes/...                         # Index files
│   │   ├── /runs/ingestion/...                  # Execution logs
│   │   └── /policies
│   │       ├── contract-families.yaml
│   │       ├── clause-taxonomy.yaml
│   │       ├── metadata-schema.yaml
│   │       ├── approval-rules.yaml              # Includes auto-approval toggle
│   │       ├── retrieval-priority.yaml
│   │       └── review-mode.yaml                 # strict / moderate / loose settings
│   │
│   ├── /matters
│   │   └── /{matter_id}
│   │       ├── matter-context.yaml              # Deal context (party, leverage, priorities)
│   │       ├── /round_1
│   │       │   ├── pipeline-state.json          # Resume state for this round
│   │       │   ├── /working/...                 # Intermediate artifacts
│   │       │   └── /source/                     # Original contract file for this round
│   │       ├── /round_2
│   │       │   ├── pipeline-state.json
│   │       │   ├── round-meta.json              # Link to prior round
│   │       │   ├── /working/...
│   │       │   └── /source/
│   │       └── /round_N/...
│   │
│   └── /output
│       └── /reports
│           ├── {matter_id}_round_{N}_redlined.docx        # Redlined contract (internal — all comments)
│           ├── {matter_id}_round_{N}_redlined_clean.docx   # Redlined contract (external-clean — [INTERNAL] stripped)
│           ├── {matter_id}_round_{N}_report.docx           # Analysis report (review)
│           ├── {matter_id}_round_{N}_delta.docx            # Delta report (re-reviews)
│           ├── {matter_id}_round_{N}_draft.docx            # Generated contract (drafting)
│           └── {matter_id}_round_{N}_review.json           # Machine-readable results
│
└── /docs
    └── implementation-notes.md                  # Implementation notes (optional)
```

### 3.2 CLAUDE.md — Core Section Inventory

CLAUDE.md serves as the main orchestrator. **It must be kept concise** — detailed behavioral rules belong in AGENT.md and SKILL.md files, not in CLAUDE.md. Long or internally conflicting CLAUDE.md content degrades adherence.

CLAUDE.md includes only the following sections:

| Section | Role |
|---------|------|
| **Identity** | One-paragraph identity statement (contract review assistant; final authority rests with the human) |
| **Workflow routing** | Rules for routing user commands to one of the five workflows; slash-command mapping (`/ingest`, `/review`, `/rereview`, `/draft`, `/library`) |
| **Sub-agent dispatch** | Conditions for calling each sub-agent; data handoff conventions (file path passing) |
| **Core safety rules** | Audience firewall, approved-only retrieval, no-auto-promotion — the non-negotiable guardrails |
| **Folder access rules** | Read/write permissions summary for each folder |
| **Error handling** | Global failure handling policy (brief) |

**Sections moved to AGENT.md or SKILL.md references** (not in CLAUDE.md):

| Content | Moved To |
|---------|----------|
| Review mode settings (strict/moderate/loose) | `contract-review/SKILL.md` references |
| Language policy | `contract-review/SKILL.md` references |
| Pipeline state management & resume protocol | `pipeline-state/SKILL.md` |
| Matter context parsing | `contract-review/SKILL.md` references |
| Drafting interview protocol | `drafting-agent/AGENT.md` |
| Human review checkpoint format | Each `AGENT.md` individually |
| Skill reference map | Each `AGENT.md` individually |

### 3.3 Agent Architecture

**Rationale for sub-agent separation:**

1. **Context window optimization**: Ingestion, review, and drafting each reference different domain knowledge (parsing guides vs. review guides vs. generation guides) and different policy files. Loading everything into a single agent wastes context budget.
2. **Clear separation of responsibility**: Ingestion owns "library construction"; review owns "contract analysis"; drafting owns "contract generation." Their inputs and outputs are distinct.
3. **Independent executability**: Ingestion can run without review, review can run in general review mode even when the library is empty, and drafting can operate in scratch mode without any library assets.

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       CLAUDE.md (Orchestrator)                            │
│                                                                           │
│  Command parsing → Workflow routing → Sub-agent dispatch                  │
│                 → Pipeline resume detection                               │
│                         → Result relay                                    │
│                                                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐      │
│  │ Ingestion Agent  │  │ Review Agent     │  │ Drafting Agent       │      │
│  │ /.claude/agents/ │  │ /.claude/agents/ │  │ /.claude/agents/     │      │
│  │ ingestion-agent/ │  │ review-agent/    │  │ drafting-agent/      │      │
│  │                 │  │                 │  │                      │      │
│  │ Skills:         │  │ Skills:         │  │ Skills:              │      │
│  │ - doc-parser    │  │ - doc-parser    │  │ - index-manager      │      │
│  │ - clause-       │  │ - clause-       │  │ - report-compiler    │      │
│  │   segmenter     │  │   segmenter     │  │ - docx-redliner      │      │
│  │ - metadata-     │  │ - index-manager │  │ - pipeline-state     │      │
│  │   validator     │  │ - report-       │  │ - contract-review    │      │
│  │ - index-manager │  │   compiler      │  │                      │      │
│  │ - contract-     │  │ - docx-redliner │  │                      │      │
│  │   review        │  │ - pipeline-state│  │                      │      │
│  │                 │  │ - contract-     │  │                      │      │
│  │                 │  │   review        │  │                      │      │
│  └─────────────────┘  └─────────────────┘  └──────────────────────┘      │
│                                                                           │
│  Shared skills: index-manager, pipeline-state, contract-review            │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Sub-Agent Definitions

#### Ingestion Agent

| Field | Detail |
|-------|--------|
| **File** | `/.claude/agents/ingestion-agent/AGENT.md` |
| **Role** | Execute the full ingestion pipeline (Workflow 1) |
| **Trigger condition** | The orchestrator detects an ingestion command |
| **Input** | File path within `inbox/raw`; optional sidecar path; optional matter ID |
| **Output** | Ingestion result JSON (success / failure / staging status, `doc_id`, summary) |
| **Referenced skills** | doc-parser, clause-segmenter, metadata-validator, index-manager, contract-review |
| **Referenced policies** | contract-families.yaml, clause-taxonomy.yaml, metadata-schema.yaml, approval-rules.yaml |
| **Human review checkpoint** | Step 9 (approval gate) |

#### Review Agent

| Field | Detail |
|-------|--------|
| **File** | `/.claude/agents/review-agent/AGENT.md` |
| **Role** | Execute the contract review pipeline (Workflow 2) and the re-review pipeline (Workflow 4) |
| **Trigger condition** | The orchestrator detects a review or re-review command |
| **Input** | Target file path; `matter_id`; optional matter context (natural language or YAML); optional `prior_round` reference |
| **Output** | Redlined DOCX + Analysis Report DOCX + Review Data JSON (+ Delta Report DOCX for re-reviews) |
| **Referenced skills** | doc-parser, clause-segmenter, index-manager, report-compiler, docx-redliner, pipeline-state, contract-review |
| **Referenced policies** | clause-taxonomy.yaml, retrieval-priority.yaml, review-mode.yaml |
| **Human review checkpoint** | Step 12 (final review) |

#### Drafting Agent

| Field | Detail |
|-------|--------|
| **File** | `/.claude/agents/drafting-agent/AGENT.md` |
| **Role** | Execute the contract drafting pipeline (Workflow 5), including structured interview, template-based or scratch generation, self-review, and DOCX production |
| **Trigger condition** | The orchestrator detects a drafting command (e.g., "draft", "작성", "create a contract") |
| **Input** | User's drafting request (natural language); optional detailed specifications |
| **Output** | Signing-ready DOCX + self-review report |
| **Referenced skills** | index-manager, report-compiler, docx-redliner (for DOCX generation), pipeline-state, contract-review |
| **Referenced policies** | contract-families.yaml, clause-taxonomy.yaml, review-mode.yaml |
| **Human review checkpoints** | Step 2 (interview summary confirmation), Step 8 (final review) |

### 3.5 Skill Inventory

| Skill | Role | Trigger Condition | Included Scripts |
|-------|------|-------------------|------------------|
| **doc-parser** | File format detection, normalization, fingerprinting | When a new document enters either pipeline (ingestion or review) | `normalize.py`, `fingerprint.py`, `detect-format.py` |
| **clause-segmenter** | Clause segmentation guidelines for LLM | After structural parse, at the clause segmentation step | LLM judgment only; `references/` directory contains guidelines |
| **index-manager** | Index CRUD operations, deterministic filter execution (including 2nd-stage narrowing filter) | At publish, search, and index rebuild operations | `build-index.py`, `query-index.py`, `supersession.py` |
| **metadata-validator** | Manifest schema validation, package integrity checks | At the validation step (Step 8) | `validate-manifest.py`, `validate-package.py`, `check-privilege-leak.py` |
| **report-compiler** | Assembly of analysis results into DOCX deliverables (analysis report + delta report) | At the report compilation step (WF2 Step 10, WF4 Step 5) | `compile-report.js`, `compile-delta-report.js` |
| **docx-redliner** | MD→DOCX clause mapping, tracked changes insertion, comment insertion | At the DOCX application steps (WF2 Steps 8–9, WF4 Step 6) | `map-clauses-to-docx.py`, `apply-redlines.py`, `apply-comments.py`, `strip-internal-comments.py` |
| **pipeline-state** | Pipeline state persistence, resume detection, round-level diff computation | At state save points and pipeline resume; at re-review diff step | `save-state.py`, `load-state.py`, `diff-rounds.py` |
| **contract-review** | Domain policy, review judgment guide, audience firewall rules, review mode definitions | At classification, comparative analysis, comment generation, and mode application steps | LLM judgment only; `references/` directory contains domain knowledge |

### 3.6 Data Handoff Conventions

| Handoff Path | Method | Format | Storage Location |
|--------------|--------|--------|------------------|
| Orchestrator → Sub-agent | Prompt inline | File path + command parameters + review mode | — |
| Sub-agent → Orchestrator | File-based + inline summary | Result JSON file path + one-line summary | `/output/` or `round_{N}/working/` |
| Inter-step intermediate artifacts | File-based | JSON, YAML, MD | Within the round directory (`matters/{matter_id}/round_{N}/working/`) |
| Index query results | Prompt inline | Filtered record list (JSON) | — (in-memory) |
| Large text payloads (full clause text) | File-based | JSON | `working/clauses/*.json` |
| Pipeline state | File-based | JSON | `round_{N}/pipeline-state.json` |
| Matter context | File-based | YAML | `matters/{matter_id}/matter-context.yaml` |

**Governing principle**: Intermediate artifacts are persisted as files within the round's working directory, and only file paths are passed between agents. Short metadata (classification results, `doc_id`, review mode, etc.) may be passed inline.

### 3.7 Primary Artifact File Formats

| Artifact | Format | Location |
|----------|--------|----------|
| Manifest | YAML | `{doc_id}/manifest.yaml` |
| Normalized text | MD, TXT | `{doc_id}/normalized/` |
| Structural parse output | JSON | `{doc_id}/structure/` |
| Cross-reference map | JSON | `{doc_id}/structure/crossref-map.json` |
| Clause records | JSON | `{doc_id}/clauses/` |
| Validation report | JSON | `{doc_id}/quality/` |
| Indexes | JSON | `/library/indexes/` |
| Policy configuration | YAML | `/library/policies/` |
| Redlined contract (internal) | DOCX | `/output/reports/{matter_id}_round_{N}_redlined.docx` |
| Redlined contract (external-clean) | DOCX | `/output/reports/{matter_id}_round_{N}_redlined_clean.docx` |
| Analysis report | DOCX | `/output/reports/{matter_id}_round_{N}_report.docx` |
| Delta report | DOCX | `/output/reports/{matter_id}_round_{N}_delta.docx` |
| Draft contract | DOCX | `/output/reports/{matter_id}_round_1_draft.docx` |
| Self-review report | JSON | `round_1/working/self-review.json` |
| Review data | JSON | `/output/reports/{matter_id}_round_{N}_review.json` |
| DOCX clause map | JSON | `round_{N}/working/docx-clause-map.json` |
| Pipeline state | JSON | `round_{N}/pipeline-state.json` |
| Round metadata | JSON | `round_{N}/round-meta.json` |
| Matter context | YAML | `matters/{matter_id}/matter-context.yaml` |
| Diff report | JSON | `round_{N}/working/diff-report.json` |
| Playbook | YAML | `/approved/playbooks/` |
| Comment bank | YAML | `/approved/comment-bank/` |
| Clause bank | JSON | `/approved/clause-bank/` |
| Ingestion run log | JSON | `/library/runs/ingestion/` |

### 3.8 Policy Files — Inventory and Customization Model

| Policy File | Role | User-Editable |
|-------------|------|---------------|
| `contract-families.yaml` | Enumeration of supported contract families. Users may freely add or remove entries. | **Yes** — primary customization entry point |
| `clause-taxonomy.yaml` | Clause type classification hierarchy. Users may extend with domain-specific types. | **Yes** — ships with a versatile default; user extends as needed |
| `metadata-schema.yaml` | Required and optional field definitions for `manifest.yaml` | Optional |
| `approval-rules.yaml` | Per-asset-type approval rules. Includes auto-approval toggle: when enabled, assets with high classification confidence and zero soft-fail conditions are automatically approved without human review. | **Yes** — auto-approval on/off is a key user setting |
| `retrieval-priority.yaml` | Retrieval priority ordering, filter rules, and exclusion rules | Optional |
| `review-mode.yaml` | Defines the three review modes (strict / moderate / loose). Each mode specifies: (1) which risk grades trigger redline suggestions, (2) which playbook tiers are considered acceptable, (3) whether comments are generated for Medium/Low items. Ships with sensible defaults; user can switch modes per review or globally. | **Yes** — controls review aggressiveness |

**Versatility strategy:**

1. `contract-families.yaml` and `clause-taxonomy.yaml` are the user-facing customization surfaces. The system ships with broadly applicable defaults (NDA, MSA, SaaS, DPA, and a generic "Other" family), but users may add, rename, or remove entries to reflect their own contracting universe.
2. Playbooks and comment banks are either authored directly by the user in YAML or auto-suggested by the agent during template ingestion.
3. No industry-specific logic exists in agent code or skill files. All domain specialization is confined to policy files and library assets. This ensures that the same codebase serves a technology company, a law firm, a game studio, or a manufacturing enterprise equally well.

### 3.9 Review Mode Definition

The `review-mode.yaml` policy file defines three modes that control the aggressiveness of contract analysis and redline generation:

| Mode | Redline Scope | Acceptable Playbook Tier | Comment Generation |
|------|---------------|--------------------------|-------------------|
| **strict** | All deviations from template | Only `preferred` | All risk levels |
| **moderate** | Critical + High risk | `preferred` + `acceptable` | Critical + High + Medium |
| **loose** | Critical only | `preferred` + `acceptable` + `fallback` | Critical + High |

- The user can set a **global default** mode in `review-mode.yaml`.
- The mode can be **overridden per review** via natural language (e.g., "review this strictly" or "do a loose review").
- When a playbook is absent for a given clause type, the matched template clause text is used as the house position baseline regardless of mode, and a `playbook_missing` flag is set in the analysis output.

### 3.10 DOCX Redline Implementation Strategy

DOCX tracked changes and comments are implemented using the **unpack → XML edit → repack** pattern from the docx skill:

1. **Unpack**: `unpack.py` extracts the DOCX into raw XML files.
2. **Apply redlines**: For each clause with a suggested redline, the script locates the target `<w:r>` elements using the clause-to-DOCX mapping, then inserts `<w:del>` and `<w:ins>` sibling elements with `w:author="Claude"`. Original `<w:rPr>` formatting is preserved.
3. **Apply comments**: `comment.py` creates comment entries in the comments XML. `<w:commentRangeStart/End>` markers are inserted as siblings of `<w:r>` in `document.xml`. Each comment is prefixed with `[INTERNAL]` or `[EXTERNAL]`.
4. **Repack**: `pack.py` reassembles and validates the DOCX.

**v1β scope limitation — body paragraphs only:**
- Redlines and comments target `<w:p>` elements in the document body.
- Tables are analyzed as clause-level units (the table as a whole), but **cell-level redlines within `<w:tc>` are deferred to v2**. Table-related comments are attached at the table-start paragraph level.
- This avoids the complexity of cell-level XML mapping while still covering the vast majority of contract clause text.

**Comment placement rules:**
- `[EXTERNAL]` comments: Only on Critical and High risk clauses (expanded by strict mode). Content is audience-safe — no internal strategy.
- `[INTERNAL]` comments: On any clause where the agent has a substantive observation. Contains reasoning, fallback positions, and negotiation notes.
- Not every redline receives a comment. Comments are reserved for items that need explanation.

**External-clean DOCX generation (v1β):**
- At the end of the review pipeline, the system **automatically produces two DOCX versions**:
  1. **Internal version** (`_redlined.docx`): Contains all redlines, `[INTERNAL]` comments, and `[EXTERNAL]` comments.
  2. **External-clean version** (`_redlined_clean.docx`): Identical to the internal version but with all `[INTERNAL]`-prefixed comments stripped. This file is safe to send to the counterparty.
- The `strip-internal-comments.py` script handles the stripping by unpacking the DOCX, removing comment entries and markers whose text starts with `[INTERNAL]`, and repacking.
- The pipeline always generates both versions. This is a **safety-critical feature**, not a convenience feature — it prevents accidental internal strategy leakage.

### 3.11 Playbook Bootstrapping

On initial setup, the library has no playbooks or comment banks. The system handles this through a dual approach:

1. **Auto-suggestion during template ingestion**: When the first template of a given `contract_family` is ingested (Workflow 1), the agent analyzes each clause and proposes a playbook draft in YAML format. The draft includes `preferred`, `acceptable`, and `fallback` tiers derived from the template's clause language. The draft is saved to `staging/` and presented to the user for review and editing before promotion to `approved/playbooks/`.

2. **Manual authoring**: Users can create or edit playbook YAML files directly in `approved/playbooks/`. The schema is documented in `metadata-schema.yaml`.

Comment banks follow the same pattern: auto-suggested during the first review cycle, then refined by the user over time.

### 3.12 Matter Context Handling

When the user provides deal context (party role, negotiation leverage, priorities), the system accepts it in two forms:

1. **Natural language** (inline in the terminal): e.g., "We're the customer, this is a standard SaaS deal, we have moderate leverage, focus on liability and data provisions."
2. **YAML file**: The user can create or edit `matters/{matter_id}/matter-context.yaml` directly.

When natural language is provided, the agent internally structures it into `matter-context.yaml`:

```yaml
party_role: customer
counterparty: "Acme Software Inc."
contract_type: saas_subscription
leverage: moderate
priority_areas:
  - limitation_of_liability
  - data_protection
notes: "Standard deal, no unusual constraints"
review_mode: moderate  # optional override
language: ko           # optional output language override
```

This file is persisted and reused across rounds within the same matter.

### 3.13 Language Policy

| Content | Language Rule |
|---------|--------------|
| Redline text (tracked changes) | Always matches the contract's original language |
| `[EXTERNAL]` comments | Matches the contract's original language |
| `[INTERNAL]` comments | Follows the report language rule below |
| Analysis report (DOCX) | If the user specifies a language → use that. Otherwise, follow the user's prompt language. |
| Delta report (DOCX) | Same as analysis report |
| Terminal output (summaries, prompts) | Follow the user's prompt language |

### 3.14 Large Document Handling

For contracts exceeding the LLM context window (typically > 100 pages of normalized text):

1. **Section-level chunking**: The document is split at section boundaries identified during structural parse (Step 3).
2. **Shared context injection**: Each chunk receives the following as prefix context:
   - `crossref-map.json` — resolving all internal references
   - `defined_terms.json` — full list of defined terms and their definitions
   - Document-level metadata (contract family, jurisdiction, parties)
3. **Parallel or sequential processing**: Chunks are processed sequentially in v1 (parallel processing is a v2 optimization opportunity).
4. **Result merging**: Per-clause analysis results from all chunks are merged into a single unified result set before report compilation.

### 3.15 Pipeline State & Resume

Each pipeline run persists its state after every step completion:

```json
{
  "pipeline": "review",
  "matter_id": "deal-2026-001",
  "round": 1,
  "last_completed_step": 7,
  "review_mode": "moderate",
  "step_artifacts": {
    "step_1": {"status": "completed", "output": "working/normalized/clean.md", "completed_at": "..."},
    "step_6": {"status": "completed", "output": "working/analysis/", "completed_at": "..."},
    "step_7": {"status": "completed", "output": "working/comments/", "completed_at": "..."}
  },
  "started_at": "2026-03-06T10:00:00Z",
  "updated_at": "2026-03-06T10:45:00Z"
}
```

**Resume protocol:**
1. On any pipeline command, the orchestrator first checks for an existing `pipeline-state.json` in the relevant round folder.
2. If a state file exists with `last_completed_step < final_step`, the agent asks: "A previous run was interrupted at Step {N}. Resume from Step {N+1}?"
3. On confirmation, the pipeline loads all intermediate artifacts from `step_artifacts` and continues from the next incomplete step.

### 3.16 Entry Points & Slash Commands

The system supports two modes of invocation: **natural language** and **explicit slash commands**. Slash commands provide stable, predictable entry points; natural language routing operates on top.

| Slash Command | Workflow | Description |
|---------------|----------|-------------|
| `/ingest` | WF1 | Ingest a document into the library |
| `/review` | WF2 | Review a counterparty contract |
| `/rereview` | WF4 | Re-review a revised contract against a prior round |
| `/draft` | WF5 | Draft a new contract (v2) |
| `/library` | WF3 | Library management commands (list, show, search, deprecate, archive) |
| `/export-clean` | Utility | Generate an external-clean DOCX (strip `[INTERNAL]` comments) |
| `/resume` | Utility | Resume an interrupted pipeline |

Each slash command is implemented as a Claude Code skill with a corresponding `SKILL.md`. Natural language commands (e.g., "이 계약서 검토해줘") are routed by the orchestrator to the appropriate slash command handler.

### 3.17 Hooks Integration

Claude Code hooks are used for automated guardrails and state management. Hooks are defined in `.claude/settings.json`.

| Hook Type | Trigger | Action |
|-----------|---------|--------|
| `PreToolUse` | Any file write operation | Verify the target path is within the allowed directory for the current workflow. Block writes outside `contract-review/`, `output/`, and the working directory. |
| `PostToolUse` | After any script execution within a pipeline step | Auto-save pipeline state (`pipeline-state.json`) to ensure resumability. |
| `SubagentStart` | When a sub-agent is dispatched | Log the sub-agent name, input parameters, and timestamp to `library/runs/audit.log`. |
| `SubagentStop` | When a sub-agent completes | Log the result summary, output paths, and duration to `library/runs/audit.log`. |

**Design rationale**: Hooks replace manual state-save calls and provide a safety net for directory protection without relying on CLAUDE.md instructions (which are context, not enforcement).

### 3.18 Retrieval Strategy

v1 does not use vector databases or embedding models. Instead, retrieval operates in four stages:

1. **Deterministic filter (Script)**: `query-index.py` reads `clauses.json` and filters by `contract_family`, `jurisdiction`, `clause_type`, `approval_state`, and `status`. This is pure JSON filtering — deterministic and fast.

2. **Narrowing filter (Script)**: If the Stage 1 result exceeds 50 candidates, a second-stage filter narrows by `contract_family` + `clause_type` combination match against each target clause. This ensures the candidate set remains manageable as the library grows.

3. **LLM-judged matching (Agent judgment)**: The filtered candidate set (typically 10–30 clauses) is presented to the LLM, which selects the best match for each target clause. Priority is given to `clause_type` alignment first, then to textual semantic similarity.

4. **Priority ranking**: The ordering defined in `retrieval-priority.yaml` (preferred template > acceptable template > approved precedent > reference-only precedent) is provided to the LLM as additional context during matching.

**Trade-offs of this approach:**
- **Strengths**: Zero external dependencies. Simple to implement. Fully auditable — the reason for each match is traceable.
- **Weaknesses**: As the library grows, the candidate set passed to the LLM may become large enough to degrade performance.
- **Mitigation**: In v2, embedding-based pre-filtering can be introduced as a refinement layer between the deterministic filter and LLM matching. In v1, the deterministic filter should be configured narrowly enough to keep candidate sets manageable.

### 3.19 Implementation Phasing

This document serves as the **target architecture and roadmap**. Implementation proceeds in phases. Each phase is independently deployable and testable.

#### Phase v1α — Core Pipeline Validation

First deployable unit. Validates the ingestion → library → review pipeline end to end, without DOCX manipulation.

**In scope:**
- Full folder structure generation
- Default policy files for all six configuration surfaces (including `review-mode.yaml`)
- Ingestion pipeline (Workflow 1) — end to end, with conditional auto-approval
- Library management (Workflow 3) — basic commands (list, show, search, deprecate, archive)
- Contract review pipeline (Workflow 2), **report-only mode**:
  - Target document parsing (Steps 1–4)
  - Library candidate retrieval with 2-stage deterministic filtering (Step 5)
  - Per-clause comparative analysis with review mode settings (Step 6)
  - Comment & redline suggestion generation (Step 7)
  - Analysis report as **JSON + MD** (no DOCX output yet)
- Index build and query
- Pipeline state persistence and resume from interruption
- Review mode settings (strict / moderate / loose)
- Natural language matter context parsing
- Cross-reference map generation for large document handling
- Explicit slash-command entry points (`/ingest`, `/review`, `/library`) alongside natural language routing
- Hooks integration (see §3.19)

#### Phase v1β — DOCX Output & Negotiation Lifecycle

Adds the signing-ready deliverables and negotiation round support.

**In scope:**
- DOCX tracked changes (redline) application via XML manipulation — **body paragraphs only** (table cell-level redline deferred to v2)
- DOCX comment insertion with `[INTERNAL]`/`[EXTERNAL]` prefix convention
- MD → DOCX clause mapping (Step 8)
- DOCX redline & comment application (Step 9)
- Analysis report generation as DOCX (Executive Summary + full analysis) (Step 10)
- **External-clean DOCX auto-generation** — automatic stripping of all `[INTERNAL]` comments to produce a counterparty-safe version alongside the internal version
- Re-review pipeline (Workflow 4) — end to end:
  - Clause-level diff between negotiation rounds
  - Full re-analysis with prior round context
  - Delta report generation (DOCX)
  - Negotiation round folder management (`round_1/`, `round_2/`, ...)
- Language-adaptive output (redline in contract language, report in prompt language)
- Slash-command entry points: `/rereview`, `/export-clean`

#### Phase v2 — Drafting & Advanced Features

**In scope:**
- Contract drafting pipeline (Workflow 5) — end to end:
  - Structured interview with adaptive depth (max 10 rounds)
  - Template-based drafting with leverage-aware clause tier selection
  - Scratch-mode drafting
  - Automated self-review before delivery
  - Signing-ready DOCX generation
  - Seamless transition to review pipeline
  - Slash-command entry point: `/draft`
- Table/exhibit cell-level DOCX redline (extending the body-paragraph model from v1β)
- Playbook auto-suggestion during template ingestion
- Delta ingestion (comparing revised versions of the same *library* document)
- Automatic supersession proposals
- Matter-to-library promotion workflow
- Embedding-based semantic retrieval
- Multi-document package ingestion (MSA + SOW + DPA bundles)
- Golden-set regression testing framework (built from v1α/v1β operational data)

---

## 4. Validation and Failure Handling Summary

**Validation philosophy**: Deterministic checks (schema validation, rule-based checks) are the **primary** validation layer and must pass before any output is accepted. LLM self-verification (e.g., "provide at least 2 reasoning sentences") is a **secondary** quality hint that improves output but is not a substitute for deterministic validation. Golden-set regression testing will be introduced in v2 once operational data from v1α/v1β has accumulated.

### 4.1 Comprehensive Validation Map

| Workflow | Step | Validation Type | Success Criteria | Failure Handling |
|----------|------|-----------------|------------------|------------------|
| WF1 | Step 1 — File detection | Rule-based | Supported format; size > 0 | Skip + log |
| WF1 | Step 2 — Fingerprint | Schema validation | `doc_id` and `sha256` generated | Duplicate → STOP |
| WF1 | Step 3 — Normalization | Rule-based | Output exists; length ≥ 50% of source | QUARANTINE |
| WF1 | Step 4 — Classification | LLM self-verification + Schema | All required axes populated; confidence ≥ medium | STAGING |
| WF1 | Step 5 — Structural parse | Schema + Rule-based | Sections ≥ 5; defined terms ≥ 1 | Retry ×1 → STAGING |
| WF1 | Step 6 — Clause segmentation | Rule-based + LLM self-verification | Clauses ≥ 5; unmapped < 30% | Retry ×1 → STAGING |
| WF1 | Step 7 — Metadata enrichment | Schema validation | All required manifest fields populated | Retry ×1 |
| WF1 | Step 8 — Validation | Rule-based + LLM | Zero hard-fail conditions | Hard → QUARANTINE; Soft → STAGING |
| WF1 | Step 9 — Approval | Conditional auto / Human review | Explicit decision exists (auto or human) | Remain waiting |
| WF1 | Step 10 — Publish | Schema validation | Asset registered in index | Retry ×1 → Escalation |
| WF2 | Steps 1–4 — Parsing | Same as WF1 Steps 3–6 | Same | Same (error report instead of QUARANTINE) |
| WF2 | Step 5 — Retrieval | Rule-based + LLM | Match rate ≥ 50% | Warning, then proceed |
| WF2 | Step 6 — Analysis | LLM self-verification | ≥ 2 reasoning sentences per judgment | Retry ×1 → "Manual review required" |
| WF2 | Step 7 — Comments | Rule-based + LLM | Critical/High have mandatory fields; audience firewall passes | Firewall violation → Regenerate ×2 → Clear + MANUAL_REQUIRED |
| WF2 | Step 8 — Clause mapping | Rule-based | ≥ 90% clause mapping coverage | Warning + proceed without unmapped redlines |
| WF2 | Step 9 — DOCX redline | Rule-based | DOCX validation passes; file opens correctly | Retry ×1 → Omit failing clause redline |
| WF2 | Step 10 — Report | Schema validation | Report structural conformance; DOCX valid | Retry ×1 |
| WF2 | Step 11 — State save | Rule-based | State file written | Log warning (non-blocking) |
| WF2 | Step 12 — Human review | Human review | Report acknowledged | Revision → Partial re-run Steps 6–10 |
| WF4 | Step 1 — Round registration | Rule-based | Round folder created; prior round exists | Error → halt |
| WF4 | Step 3 — Clause diff | Rule-based + LLM | All clauses classified (unchanged/modified/added/removed) | Retry ×1 |
| WF4 | Step 4 — Re-analysis | LLM self-verification | All clauses have delta_summary | Retry ×1 |
| WF4 | Step 5 — Delta report | Schema validation | Report contains all four sections | Retry ×1 |
| WF5 | Step 1 — Interview | LLM self-verification | Essential fields populated (type, parties, terms) | Proceed with defaults after 10 rounds |
| WF5 | Step 2 — Summary | Human review | User confirms summary | Re-present with corrections |
| WF5 | Step 4 — Template lookup | Rule-based | Template found or scratch mode acknowledged | Proceed in scratch mode |
| WF5 | Step 5 — Generation | LLM self-verification | Complete contract, no placeholders, consistent terms | Retry ×1 |
| WF5 | Step 6 — Self-review | LLM + Rule-based | Zero critical issues; no unfilled placeholders | Auto-fix + flag remainder |
| WF5 | Step 7 — DOCX generation | Rule-based | DOCX validation passes; file size > 0 | Retry ×1 |
| WF5 | Step 8 — Human review | Human review | Draft acknowledged | Revision → re-run Steps 5–7 |

### 4.2 Global Failure Handling Policy

| Situation | Handling |
|-----------|----------|
| Script runtime error | Log the error, display a message to the user, halt the pipeline |
| LLM response parsing failure | Automatic retry ×1 (re-emphasize output format). On second failure → escalation |
| Filesystem access error | Log the error, halt the pipeline, request path verification from the user |
| Index corruption detected | Advise the user to run the `rebuild-index` command |
| Unexpected error | Log the error + explain the situation to the user + request manual intervention |

---

## 5. Initial Setup Procedure

When implementing, proceed in phases. **v1α** is the first deployable unit:

### v1α Setup

1. **Generate folder structure** — Run a setup script to create the entire directory tree defined in Section 3.1
2. **Generate default policy files** — Author the six policy YAML files with versatile default values (including `review-mode.yaml`)
3. **Configure hooks** — Set up `.claude/settings.json` with the hooks defined in Section 3.17
4. **Implement scripts** — Build the scripts within doc-parser, index-manager, metadata-validator, and pipeline-state
5. **Author skill files** — Write each SKILL.md with LLM guidelines and behavioral instructions; create slash-command skills (`/ingest`, `/review`, `/library`)
6. **Author sub-agent files** — Write AGENT.md for ingestion-agent and review-agent
7. **Author CLAUDE.md** — Write the orchestrator instructions (**keep concise** — see Section 3.2 for scope)
8. **Run the first ingestion test** — Process a single NDA template through the full pipeline to verify end-to-end operation
9. **Run the first review test** — Submit a counterparty NDA for review against the registered template, verify JSON/MD report output

### v1β Setup (after v1α is stable)

10. **Implement DOCX scripts** — Build docx-redliner and report-compiler scripts
11. **Implement external-clean generation** — Build and test `strip-internal-comments.py`
12. **Author slash-command skills** — `/rereview`, `/export-clean`
13. **Run the first DOCX review test** — Verify redlined DOCX + external-clean DOCX generation
14. **Run the first re-review test** — Submit a revised NDA as round 2 and verify delta report generation

### v2 Setup (after v1β is stable)

15. **Author drafting-agent AGENT.md** — Include interview protocol, template lookup, self-review logic
16. **Implement drafting scripts** — Contract generation, DOCX formatting
17. **Run the first drafting test** — Request an NDA draft, verify interview → DOCX generation → self-review flow

---

## 6. Expansion Roadmap

| Version | Additions |
|---------|-----------|
| **v1α** | Ingestion + library management + review (JSON/MD report) + pipeline state + hooks + slash commands |
| **v1β** | DOCX redline/comments (body paragraph) + external-clean auto-generation + re-review delta + DOCX reports |
| **v2.0** | Contract drafting pipeline + table/exhibit cell-level redline + playbook auto-suggestion + golden-set testing |
| **v2.1** | Delta ingestion for library documents; matter-to-library promotion |
| **v3.0** | Embedding-based retrieval; multi-document package ingestion; advanced negotiation analytics |

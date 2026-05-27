<div align="center">

# Contract Review Agent

### AI-Powered Contract Review Workflow for KP Legal Orchestrator

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Claude Code](https://img.shields.io/badge/Built_with-Claude_Code-blueviolet)](https://claude.ai/claude-code)
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-green)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)](https://www.python.org/)

[English](./README.md)&ensp;·&ensp;[한국어](./docs/ko/README.md)

---

Drop a contract in, get back a **Word file with tracked-change redlines,
margin comments (internal strategy + external-facing), a full analysis report,
and negotiation recommendations** — all generated directly in DOCX.

**Final legal judgment stays with the human.**

</div>

> [!IMPORTANT]
> **Before you start, please read:**
> - **[Disclaimer](./docs/en/DISCLAIMER.md)** — important limitations and data security considerations
> - **[How to Use](./docs/en/HOW-TO-USE.md)** — setup, environment, and step-by-step guide
> - **[Seed Calibration Playbook](./docs/en/SEED-CALIBRATION-PLAYBOOK.md)** — advanced operating guide for maintaining synthetic library baselines over time

## What It Does

<table>
<tr>
<td width="80" align="center"><h3>1</h3></td>
<td>
<strong>Ingest</strong><br/>
Build a searchable library from your house templates, precedents, and playbooks
</td>
</tr>
<tr>
<td align="center"><h3>2</h3></td>
<td>
<strong>Review</strong><br/>
Clause-by-clause analysis of counterparty paper against your house positions
</td>
</tr>
<tr>
<td align="center"><h3>3</h3></td>
<td>
<strong>Re-review</strong><br/>
Delta analysis when a revised draft comes back from negotiation
</td>
</tr>
<tr>
<td align="center"><h3>4</h3></td>
<td>
<strong>Draft</strong><br/>
Interview-driven contract generation with self-review
</td>
</tr>
</table>

> All processing runs **locally on your filesystem** — no external servers, no vector databases, no data leaves your machine.

---

## Quick Start

### Step 1 — Install

```bash
git clone <repository-url> contract-review-agent
cd contract-review-agent
npm install
python -m pip install pyyaml
```

### Step 2 — Customize Policies to Your Practice

Policy files control how the agent classifies and reviews contracts. They ship with broad defaults covering 29 contract families, but you should tailor them to your practice.

On first run, default policies are automatically copied from `policies.default/` to `policies/`. Your customizations in `policies/` are gitignored — they won't be overwritten by `git pull`.

Ask Claude Code directly — in the terminal or the extension chat panel. It can rewrite all six policy files (contract families, clause taxonomy, review modes, retrieval rules, etc.) in one pass. You can also [edit the YAML files manually](#-policy-files).

> [!TIP]
> **Not sure how to configure policies yet?** Skip to Step 3 first. Ingest your house templates, then come back and ask Claude Code to customize the policies based on the ingested contracts. This is often easier than writing policy specs from scratch — let your actual contracts drive the configuration.

### Step 3 — Seed Your Library

Drop your house templates and reference contracts into [`contract-review/library/inbox/raw/`](./contract-review/library/inbox/raw/), then type (in the terminal or extension chat):

```text
/ingest
```

| Guideline | Detail |
|-----------|--------|
| Volume | **50 documents or fewer** for initial setup. Add more anytime. |
| Formats | DOCX, PDF, Markdown |
| Structure | One agreement per file |
| Privacy | All uploaded files stay on your local PC only — they are never uploaded or shared anywhere |

Templates and precedents are **auto-approved** by default. Playbooks and comment banks still require human confirmation. See [`approval-rules.yaml`](./contract-review/library/policies/approval-rules.yaml).

> [!TIP]
> **Redlined contracts too.** Drop a DOCX with tracked changes and comments into the same `inbox/raw/` folder. The system auto-detects tracked changes and extracts *what* was changed, *how*, and *why* — building a personalized review pattern index. Over time, this lets the agent reference your past negotiation patterns during future reviews.

### Step 4 — Review a Contract

Drop the contract you want reviewed into [`contract-review/workspace/input/`](./contract-review/workspace/input/) (preferred) or the legacy [`input/`](./input/) folder, then type:

```text
/contract-review
```

Results (redlined DOCX, analysis report, etc.) are saved to [`contract-review/workspace/output/`](./contract-review/workspace/output/) by default. The legacy [`output/`](./output/) folder remains supported for existing workflows.

Both the workspace folders and legacy `input/` / `output/` folders are excluded from version control — your contract files never leave your local PC.

---

## Commands

| Command | What it does |
|---------|-------------|
| `/ingest` | Ingest documents into the library (clean templates or redlined contracts — auto-detected) |
| `/contract-review` | Review a counterparty contract |
| `/rereview` | Re-review a revised draft against a prior round |
| `/library` | Search, list, show, deprecate, or archive library assets |
| `/export-clean` | Strip `[INTERNAL]` comments from a redlined DOCX |
| `/resume` | Resume an interrupted pipeline |
| `/draft` | Draft a new contract with interview-driven generation and DOCX export |

Natural language works too — the orchestrator routes to the right workflow.

---

## How It Works

### Review Pipeline

```
  Target contract (DOCX/PDF)
      |
      v
  +-----------------------+
  |  Parse & Segment      |  Break into individual clauses
  +-----------------------+
      |
      v
  +-----------------------+
  |  Library Retrieval    |  Match against house clauses
  +-----------------------+
      |
      v
  +-----------------------+
  |  Clause Comparison    |  Risk grading + gap analysis
  +-----------------------+
      |
      v
  +-----------------------+
  |  Generate Redlines    |  Tracked changes + comments
  +-----------------------+
      |
      +------+------+------+
      |      |      |
      v      v      v
    Internal  External  Review
    Redline   Clean     Report
    DOCX      DOCX      DOCX
```

### Review Modes

| Mode | When to use | Redline scope |
|------|------------|---------------|
| **`strict`** | High-value deals, M&A, strong leverage | All deviations |
| **`moderate`** | Standard commercial deals | Critical + High risk |
| **`loose`** | Low leverage, quick assessments, LOI/MOU | Critical only |

Default is `moderate`. You can override it per review with a natural-language request.

### Library Ingestion

```
inbox/raw/  ──>  validate  ──>  classify  ──>  segment  ──>  approved/
                    │                                            ├── templates/
                    │                                            ├── precedents/
                    │                                            └── redline-records/
                    │                 \
                    │                  └──>  quarantine/  (on failure)
                    │
                    └──  tracked changes detected?
                              │
                              └──>  extract-redlines.py  ──>  redline_record pathway
                                    (changes.json, comments.json, review patterns)
```

Auto-approval is on by default for templates, precedents, and redline records. No manual approval step needed.

### Adding Reference Sources

Beyond contract templates, you can build a **reference library** of statutes, court decisions, law firm analyses, forms, and more. These are converted to structured Markdown and used as context during reviews.

1. Drop any file (PDF, DOCX, etc.) into `contract-review/library/inbox/raw/`
2. Tell the agent: `/ingest` or "참조 자료 넣었어"
3. The agent will automatically:
   - Convert to structured Markdown
   - Generate metadata (frontmatter)
   - Place in `library/sources/`
   - Update search indexes

> **Note:** Dropping files alone does not trigger processing.
> You must run `/ingest` or tell the agent to start the parsing pipeline.

### Retrieval Strategy

No embeddings or vector databases. Retrieval works in stages:

1. **Deterministic filter** — JSON index filtering by contract family, jurisdiction, governing law, approval state, and status
2. **Narrowing** — structural clause-type matching when candidates exceed threshold
3. **Priority ranking** — controlled by [`retrieval-priority.yaml`](./contract-review/library/policies/retrieval-priority.yaml), including authority-level ranking, same-language preference, freshness downranking, and affinity-family fallback
4. **LLM judgment** — best-match selection from the filtered set

Fully auditable. Every match is traceable.

---

## Repository Layout

```
.
├── input/                       # Legacy contract drop zone (gitignored)
├── output/                      # Legacy review results (gitignored)
│
├── .claude/
│   ├── agents/                  # Sub-agents: ingestion, review, drafting
│   ├── skills/                  # Skills: parsing, indexing, validation, redlining, etc.
│   ├── hooks/                   # UserPromptSubmit hook (domain reference injector)
│   ├── scripts/                 # Loader script + test scripts
│   └── settings*.json           # Optional local Claude Code settings (gitignored)
│
├── contract-review/
│   ├── workspace/               # Preferred local runtime workspace (gitignored)
│   │   ├── input/               # Drop contracts to review here
│   │   ├── output/              # Review results appear here
│   │   ├── logs/                # Session notes
│   │   ├── matters/             # Matter working directories
│   │   └── runs/                # Runtime traces
│   ├── library/
│   │   ├── inbox/raw/           # Drop source templates here (gitignored)
│   │   ├── inbox/sidecars/      # Auxiliary metadata (gitignored)
│   │   ├── staging/             # Validated, awaiting approval (gitignored)
│   │   ├── approved/            # Published assets (local runtime assets gitignored; bundled seeds tracked)
│   │   │   ├── templates/       #   Clean contract templates
│   │   │   ├── precedents/      #   Precedent agreements
│   │   │   └── redline-records/ #   Ingested redlined contracts (review pattern data)
│   │   ├── quarantine/          # Failed / rejected (gitignored)
│   │   ├── sources/             # Reference sources (statutes, precedents, and other supporting materials)
│   │   ├── indexes/             # Local generated JSON indexes (gitignored)
│   │   ├── policies/            # Your customized config (gitignored)
│   │   ├── policies.default/    # Shipped defaults (do not edit)
│   │   └── runs/
│   │       ├── ingestion/       # Local ingestion run artifacts (gitignored)
│   │       └── sessions/        # Per-execution forensic traces (gitignored)
│   └── matters/                 # Legacy per-deal working directories (gitignored)
│
├── logs/                        # Session logs — your conversation notes (gitignored)
├── docs/
├── CLAUDE.md                    # Orchestrator routing rules
└── package.json
```

### Session Logs

The `logs/` folder is your personal workspace for saving conversation notes, analysis records, and session history. Files in this folder are gitignored — they stay on your machine and are never committed.

Use it to keep track of review decisions, negotiation strategy discussions, or any context you want to carry across sessions. Claude Code will save session summaries here when asked.

---

## Policy Files

Six YAML files under `contract-review/library/policies/` control the agent's behavior. These are the primary customization surface.

> [!NOTE]
> `policies/` is gitignored — your customizations are safe from `git pull`. Defaults are shipped in `policies.default/` and auto-copied on first run.

| File | Controls | Edit? |
|------|----------|-------|
| `contract-families.yaml` | Supported agreement types (29 families) | **Yes** |
| `clause-taxonomy.yaml` | Clause classification hierarchy | **Yes** |
| `review-mode.yaml` | Strict / moderate / loose review settings + recommended modes per deal type | **Yes** |
| `approval-rules.yaml` | Auto-approval toggle and per-asset-type rules | **Yes** |
| `retrieval-priority.yaml` | Search ranking, language preference, freshness handling, and affinity fallback | Optional |
| `metadata-schema.yaml` | Metadata field definitions | Optional |

Policies are **read-only for the agent** — only you edit them. The agent manages `indexes/` automatically as local generated artifacts; index JSON files are gitignored because they can contain text derived from local library assets.

---

## Prerequisites

| Requirement | Version | Install |
|-------------|---------|---------|
| Python | 3.10+ | — |
| Node.js | 18+ | — |
| PyYAML | — | `pip install pyyaml` |
| `jq` | 1.6+ | `brew install jq` (macOS) · `apt-get install jq` (Linux) |
| `shasum` or `sha256sum` | — | Preinstalled on macOS / most Linux distros |

Optional: `pymupdf` or `pypdf` (PDF support), `pandoc` (enhanced DOCX conversion).

> [!IMPORTANT]
> `jq` is required by the domain reference forced-load hook (`.claude/hooks/inject-domain-references.sh`) and the loader script. Without it, the hook can only emit an error and no context injection, while direct loader/pre-pipeline calls exit non-zero. Install `jq` before running review workflows so digest traces and section loads are available.

---

## Architecture

The agent is composed of three specialized sub-agents coordinated by an orchestrator (`CLAUDE.md`):

```
                    ┌─────────────────────┐
                    │    Orchestrator      │
                    │    (CLAUDE.md)       │
                    └──────┬──────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            v              v              v
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Ingestion │  │   Review   │  │  Drafting  │
   │   Agent    │  │   Agent    │  │   Agent    │
   └────────────┘  └────────────┘  └────────────┘
```

<details>
<summary><strong>Key architectural choices</strong></summary>
<br/>

- **No embeddings / no vector DB** — retrieval uses deterministic JSON index filtering + LLM judgment
- **Pipeline state persistence** — each step writes `pipeline-state.json`, enabling resume after interruption
- **Audience firewall** — `[INTERNAL]` and `[EXTERNAL]` comment streams are strictly separated at every stage
- **File-based data handoff** — large payloads pass between agents as local files under `contract-review/workspace/matters/` or `contract-review/workspace/runs/` (legacy `matters/` and `library/runs/` remain supported), not inline

</details>

---

## Design Principles

| Principle | Description |
|-----------|-------------|
| **Human in the loop** | The agent proposes, the human decides |
| **Local and auditable** | All data on disk, all artifacts inspectable |
| **Audience firewall** | Internal strategy never leaks into external-facing output |
| **Resume-friendly** | Pipelines persist state and can resume after interruption |
| **Industry-agnostic** | All domain specialization lives in policy files, not code |

---

## Roadmap

| Phase | Scope |
|-------|-------|
| **v1-alpha** | Ingestion, library management, review (JSON/MD reports), pipeline state, slash commands |
| **v1-beta** | DOCX redlines/comments, external-clean export, re-review delta reports, **redline record ingestion (review pattern personalization)** |
| **v2** | Contract drafting, table-level redlines, playbook auto-suggestion, embedding retrieval |

---

## Reference

- [How to Use](./docs/en/HOW-TO-USE.md) — setup guide and step-by-step walkthrough
- [CLAUDE.md](./CLAUDE.md) — orchestrator routing and safety rules

Internal implementation notes are kept in the local-only workspace and are intentionally omitted from the public repository.

## Part of KP Legal Orchestrator

This agent is part of the **KP Legal Orchestrator** family of specialist legal workflow agents.
Representative repositories in the ecosystem are listed below by repository ID:

| Repository ID | Role | Focus |
|-------|---------|-------|
| `legal-research-agent` | Legal Research Specialist | Legal research |
| `legal-translation-agent` | Legal Translation Specialist | Legal translation |
| `data-protection-agent` | Data Protection Specialist | Data protection |
| **`contract-review-agent`** | **Contract Review Specialist** | **Contract review** |
| `legal-writing-agent` | Legal Drafting Specialist | Legal writing |
| `second-review-agent` | Senior Review Specialist | Quality review |

## License

Licensed under the [Apache License, Version 2.0](LICENSE). See [LICENSE](./LICENSE).

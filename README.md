# Contract Review Agent

> AI-powered contract review pipeline built on Claude Code.
> Drop a contract in, get back a **Word file with tracked-change redlines, margin comments (internal strategy + external-facing), a full analysis report, and negotiation recommendations** — all generated directly in DOCX.
> Final legal judgment stays with the human.

**[Disclaimer](./docs/DISCLAIMER.md)** | **[How to Use](./docs/HOW-TO-USE.md)**

---

## Overview

Contract Review Agent is a **Claude Code-native** project for legal contract operations:

| Capability | Description |
|------------|-------------|
| **Ingest** | Build a searchable library from your house templates, precedents, and playbooks |
| **Review** | Clause-by-clause analysis of counterparty paper against your house positions |
| **Re-review** | Delta analysis when a revised draft comes back from negotiation |
| **Draft** | Interview-driven contract generation with self-review *(roadmap)* |

All processing runs **locally on your filesystem** — no external servers, no vector databases, no data leaves your machine.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/kipeum86/contract-review-agent.git
cd contract-review-agent
npm install
python -m pip install pyyaml
```

### 2. Customize Policies to Your Practice

The policy files in [`contract-review/library/policies/`](./contract-review/library/policies/) control how the agent classifies and reviews contracts. They ship with broad defaults covering 27 contract families, but you should tailor them to your practice.

Ask Claude Code directly:

```text
Rewrite the policy files to match the contract types I work with.

Contract types I handle:
- NDA, license, IP assignment, content distribution, game development, ...
```

Claude Code will rewrite all six policy files (contract families, clause taxonomy, review modes, retrieval rules, etc.) in one pass. You can also [edit the YAML files manually](#policy-files).

> **Tip — Not sure how to configure policies yet?** Skip to Step 3 first. Ingest your house templates, then come back and ask Claude Code to customize the policies based on the ingested contracts:
>
> ```text
> ingest된 계약서 유형에 맞게 policies파일 수정해줘.
> Rewrite policies to match the contra2ct types already in my library.
> ```
>
> This is often easier than writing policy specs from scratch — let your actual contracts drive the configuration.

### 3. Seed Your Library

Drop your house templates and reference contracts into [`contract-review/library/inbox/raw/`](./contract-review/library/inbox/raw/), then run:

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

### 4. Review a Contract

Drop the contract you want reviewed into the [`input/`](./input/) folder at the project root, then run:

```text
/contract-review
```

Results (redlined DOCX, analysis report, etc.) are saved to the [`output/`](./output/) folder.

Both `input/` and `output/` are excluded from version control — your contract files never leave your local PC.

Natural language also works:

```text
이 SaaS 계약서 moderate 모드로 검토해줘.
Review this NDA strictly.
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `/ingest` | Ingest documents into the library |
| `/contract-review` | Review a counterparty contract |
| `/rereview` | Re-review a revised draft against a prior round |
| `/library` | Search, list, show, deprecate, or archive library assets |
| `/export-clean` | Strip `[INTERNAL]` comments from a redlined DOCX |
| `/resume` | Resume an interrupted pipeline |
| `/draft` | Draft a new contract *(roadmap — v2)* |

Natural language works too — the orchestrator routes to the right workflow.

---

## How It Works

### Review Pipeline

```
Target contract (DOCX/PDF)
    │
    ├── Parse & segment into clauses
    ├── Retrieve matching house clauses from library
    ├── Compare clause-by-clause (risk grading, gap analysis)
    ├── Generate redline suggestions + comments
    ├── Apply tracked changes to DOCX
    │
    ├── 📄 Internal redlined DOCX   (all comments)
    ├── 📄 External-clean DOCX      ([INTERNAL] stripped — safe for counterparty)
    └── 📄 Review report DOCX       (executive summary + full analysis)
```

### Review Modes

| Mode | When to use | Redline scope |
|------|------------|---------------|
| **strict** | High-value deals, M&A, strong leverage | All deviations |
| **moderate** | Standard commercial deals | Critical + High risk |
| **loose** | Low leverage, quick assessments, LOI/MOU | Critical only |

Default is `moderate`. Override per-review: `"이거 엄격하게 검토해줘"` or `"do a loose review"`.

### Library Ingestion

```
inbox/raw/  ──→  validate  ──→  classify  ──→  segment  ──→  approved/
                                                    ↘
                                                 quarantine/  (on failure)
```

Auto-approval is on by default for templates and precedents. No manual approval step needed.

### Retrieval Strategy

No embeddings or vector databases. Retrieval works in stages:

1. **Deterministic filter** — JSON index filtering by contract family, clause type, jurisdiction
2. **Narrowing** — structural attribute matching when candidates exceed threshold
3. **LLM judgment** — best-match selection from the filtered set
4. **Priority ranking** — controlled by [`retrieval-priority.yaml`](./contract-review/library/policies/retrieval-priority.yaml)

Fully auditable. Every match is traceable.

---

## Repository Layout

```
.
├── input/                       # ⬅ Drop contracts to review here (gitignored)
├── output/                      # ⬅ Review results appear here (gitignored)
│
├── .claude/
│   ├── agents/                  # Sub-agents: ingestion, review, drafting
│   ├── skills/                  # Skills: parsing, indexing, validation, redlining, etc.
│   └── settings.json
│
├── contract-review/
│   ├── library/
│   │   ├── inbox/raw/           # Drop source templates here (gitignored)
│   │   ├── inbox/sidecars/      # Auxiliary metadata (gitignored)
│   │   ├── staging/             # Validated, awaiting approval (gitignored)
│   │   ├── approved/            # Published assets (gitignored)
│   │   ├── quarantine/          # Failed / rejected (gitignored)
│   │   ├── indexes/             # JSON indexes (auto-managed)
│   │   └── policies/            # YAML config files (user-managed)
│   └── matters/                 # Per-deal working directories (gitignored)
│
├── docs/
├── CLAUDE.md                    # Orchestrator routing rules
├── contract-review-agent-design.md  # Full architecture document
└── package.json
```

---

## Policy Files

Six YAML files under [`contract-review/library/policies/`](./contract-review/library/policies/) control the agent's behavior. These are the primary customization surface.

| File | Controls | Edit? |
|------|----------|-------|
| `contract-families.yaml` | Supported agreement types (27 families: NDA, SPA, game dev, publishing, ...) | **Yes** |
| `clause-taxonomy.yaml` | Clause classification hierarchy (M&A, IP, content, game dev categories, ...) | **Yes** |
| `review-mode.yaml` | Strict / moderate / loose review settings + recommended modes per deal type | **Yes** |
| `approval-rules.yaml` | Auto-approval toggle and per-asset-type rules | **Yes** |
| `retrieval-priority.yaml` | Search ranking, affinity groups for cross-family matching | Optional |
| `metadata-schema.yaml` | Metadata field definitions (bilingual support, industry tags, ...) | Optional |

Policies are **read-only for the agent** — only you edit them. The agent manages `indexes/` automatically.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.14+ |
| Node.js | 24+ |
| PyYAML | `pip install pyyaml` |

Optional: `pymupdf` or `pypdf` (PDF support), `pandoc` (enhanced DOCX conversion).

---

## Design Principles

- **Human in the loop** — the agent proposes, the human decides
- **Local and auditable** — all data on disk, all artifacts inspectable
- **Audience firewall** — internal strategy never leaks into external-facing output
- **Resume-friendly** — pipelines persist state and can resume after interruption
- **Industry-agnostic** — all domain specialization lives in policy files, not code

---

## Roadmap

| Phase | Scope |
|-------|-------|
| **v1-alpha** | Ingestion, library management, review (JSON/MD reports), pipeline state, slash commands |
| **v1-beta** | DOCX redlines/comments, external-clean export, re-review delta reports |
| **v2** | Contract drafting, table-level redlines, playbook auto-suggestion, embedding retrieval |

---

## Reference

- [Architecture & Design Document](./contract-review-agent-design.md) — full workflow specs, folder schema, implementation phases
- [CLAUDE.md](./CLAUDE.md) — orchestrator routing and safety rules
- [Implementation Notes](./docs/implementation-notes.md) — repository implementation details

## License

MIT — see [LICENSE](./LICENSE).

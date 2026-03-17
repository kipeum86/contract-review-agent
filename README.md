<div align="center">

# Contract Review Agent

### AI-Powered Contract Review Pipeline Built on Claude Code

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
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

---

## Example Outputs

<table>
<tr>
<th width="120">Language</th>
<th>Redlined DOCX</th>
<th>Review Report</th>
</tr>
<tr>
<td><strong>English</strong></td>
<td><a href="https://docs.google.com/document/d/1KIIW5lY-H-LddPgUGWLiA1kcFQxbJECq/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">Redlined DOCX</a></td>
<td><a href="https://docs.google.com/document/d/1QinVyQHdyb5VxxkjpmFVdVYgFoxgwX0e/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">Client Memo</a></td>
</tr>
<tr>
<td><strong>한국어</strong></td>
<td><a href="https://docs.google.com/document/d/1g6AFUqiJp8fCb_3NayHfNhqRDFAq6c0Q/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">레드라인 DOCX</a></td>
<td><a href="https://docs.google.com/document/d/1y_iMJBNwlvubzs1wfcLq1q8lNL3pQxXQ/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true">검토 의견서</a></td>
</tr>
</table>

---

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
git clone https://github.com/kipeum86/contract-review-agent.git
cd contract-review-agent
npm install
python -m pip install pyyaml
```

### Step 2 — Customize Policies to Your Practice

The policy files in [`contract-review/library/policies/`](./contract-review/library/policies/) control how the agent classifies and reviews contracts. They ship with broad defaults covering 27 contract families, but you should tailor them to your practice.

Ask Claude Code directly — in the terminal or the extension chat panel:

```text
Rewrite the policy files to match the contract types I work with.

Contract types I handle:
- NDA, license, IP assignment, content distribution, game development, ...
```

Claude Code will rewrite all six policy files (contract families, clause taxonomy, review modes, retrieval rules, etc.) in one pass. You can also [edit the YAML files manually](#-policy-files).

> [!TIP]
> **Not sure how to configure policies yet?** Skip to Step 3 first. Ingest your house templates, then come back and ask Claude Code to customize the policies based on the ingested contracts:
>
> ```text
> ingest된 계약서 유형에 맞게 policies파일 수정해줘.
> Rewrite policies to match the contract types already in my library.
> ```
>
> This is often easier than writing policy specs from scratch — let your actual contracts drive the configuration.

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

### Step 4 — Review a Contract

Drop the contract you want reviewed into the [`input/`](./input/) folder at the project root, then type:

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
| `/draft` | Draft a new contract |

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

<details>
<summary><strong>Example Output</strong> — see what the deliverables actually look like</summary>
<br/>

| Deliverable | Language | Link |
|-------------|----------|------|
| Client Memo | English | [View on Google Docs](https://docs.google.com/document/d/1QinVyQHdyb5VxxkjpmFVdVYgFoxgwX0e/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |
| Contract Redlined | English | [View on Google Docs](https://docs.google.com/document/d/1KIIW5lY-H-LddPgUGWLiA1kcFQxbJECq/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |
| 검토 의견서 | 한국어 | [Google Docs에서 보기](https://docs.google.com/document/d/1y_iMJBNwlvubzs1wfcLq1q8lNL3pQxXQ/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |
| 계약서 검토본 | 한국어 | [Google Docs에서 보기](https://docs.google.com/document/d/1g6AFUqiJp8fCb_3NayHfNhqRDFAq6c0Q/edit?usp=sharing&ouid=105178834220477378953&rtpof=true&sd=true) |

</details>

### Review Modes

| Mode | When to use | Redline scope |
|------|------------|---------------|
| **`strict`** | High-value deals, M&A, strong leverage | All deviations |
| **`moderate`** | Standard commercial deals | Critical + High risk |
| **`loose`** | Low leverage, quick assessments, LOI/MOU | Critical only |

Default is `moderate`. Override per-review: `"이거 엄격하게 검토해줘"` or `"do a loose review"`.

### Library Ingestion

```
inbox/raw/  ──>  validate  ──>  classify  ──>  segment  ──>  approved/
                                                   \
                                                    └──>  quarantine/  (on failure)
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
├── input/                       # Drop contracts to review here (gitignored)
├── output/                      # Review results appear here (gitignored)
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
| Python | 3.10+ |
| Node.js | 18+ |
| PyYAML | `pip install pyyaml` |

Optional: `pymupdf` or `pypdf` (PDF support), `pandoc` (enhanced DOCX conversion).

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
- **File-based data handoff** — large payloads pass between agents as files under `matters/` or `library/runs/`, not inline

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
| **v1-beta** | DOCX redlines/comments, external-clean export, re-review delta reports |
| **v2** | Contract drafting, table-level redlines, playbook auto-suggestion, embedding retrieval |

---

## Reference

- [How to Use](./docs/en/HOW-TO-USE.md) — setup guide and step-by-step walkthrough
- [CLAUDE.md](./CLAUDE.md) — orchestrator routing and safety rules
- [Implementation Notes](./docs/en/implementation-notes.md) — repository implementation details

## License

MIT — see [LICENSE](./LICENSE).

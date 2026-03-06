# Contract Review Agent

Contract Review Agent is a Claude Code-native contract operations project for ingesting legal know-how, reviewing counterparty paper, supporting negotiation re-reviews, and eventually drafting contracts. The design centers on a simple principle: the agent does the repetitive analysis and document preparation work, but final legal judgment remains with the human reviewer.

This repository should be read as both:

- a working Claude Code project scaffold with skills, agents, policies, and helper scripts
- a design-first implementation of the target architecture described in [`contract-review-agent-design.md`](./contract-review-agent-design.md)

## What This Project Is For

The system is designed to help a single legal operator or team lead:

- ingest reusable contracting assets into a local house library
- review third-party drafts clause by clause against approved internal positions
- generate redline suggestions, internal notes, and external-safe comments
- preserve negotiation history across rounds
- keep all processing local to the filesystem and Claude Code workflow

## Design Principles

- Human in the loop: the agent proposes, the human approves.
- Local and auditable: data lives on disk; artifacts and indexes are inspectable.
- No vector database by default: retrieval uses deterministic filtering plus LLM judgment.
- Approved-only authority: only approved, active library assets should be treated as house position.
- Audience firewall: internal strategy must never leak into external-facing output.
- Resume-friendly pipelines: long workflows persist state and can be resumed after interruption.

## Repository Status

This repository already contains the core project skeleton and a substantial portion of the helper logic:

- `CLAUDE.md` routing rules for the overall orchestrator
- `.claude/agents/` sub-agents for ingestion, review, and drafting
- `.claude/skills/` skills for parsing, segmentation, indexing, validation, reporting, DOCX redlining, pipeline state, and contract-review guidance
- Python helper scripts for parsing, indexing, validation, resume state, and DOCX XML manipulation
- Node.js report compilers for DOCX report generation
- seed policy YAML files and empty JSON indexes under `contract-review/library/`

What this repository is not yet:

- a packaged standalone CLI application
- a conventional Node.js app with runnable `npm` scripts for the full pipeline
- a fully productionized distribution with sample datasets, test coverage, and end-user installers

In other words, the repo already implements important building blocks, but the design document still represents the broader target architecture and roadmap.

## Core Workflows

### 1. Library Ingestion

The ingestion flow takes source documents such as templates, playbooks, precedents, and comment banks, then:

1. detects the file format
2. fingerprints the file and checks duplicates
3. normalizes content to machine-usable text
4. classifies and routes the document
5. parses structure and segments clauses
6. enriches metadata
7. validates the package and applies approval rules
8. publishes approved assets and rebuilds indexes

### 2. Contract Review

The review flow parses a target contract, retrieves relevant library candidates, performs clause-by-clause comparative analysis, and prepares:

- redline suggestions
- internal and external comment candidates
- structured review JSON
- a review report

The design supports review modes such as `strict`, `moderate`, and `loose`, configured in [`contract-review/library/policies/review-mode.yaml`](./contract-review/library/policies/review-mode.yaml).

### 3. Library Management

The library workflow handles listing, searching, showing, deprecating, archiving, and rebuilding metadata/index state for approved assets.

### 4. Re-review

The re-review workflow compares a revised draft against a prior negotiation round, identifies changed clauses, and produces delta-focused analysis.

### 5. Drafting

The design also includes a drafting workflow for interview-based or prompt-based contract generation, followed by self-review and DOCX output. This is part of the target architecture and should be treated as roadmap-driven unless you have wired the full drafting flow in your Claude Code environment.

## How The System Works

### Invocation Model

The project is designed for Claude Code, not for direct use as a traditional web service. The primary entry points are slash commands or natural-language routing:

- `/ingest`
- `/review`
- `/rereview`
- `/draft`
- `/library`
- `/export-clean`
- `/resume`

### Retrieval Strategy

The design intentionally avoids embeddings and vector infrastructure in the default architecture. Retrieval is done in stages:

1. deterministic JSON filtering over indexed metadata
2. candidate narrowing using structural attributes such as contract family and clause type
3. LLM judgment over the filtered set
4. priority ordering controlled by policy files

This keeps the system easy to audit and operate locally, at the cost of some scalability compared with embedding-heavy retrieval systems.

### DOCX Output Strategy

DOCX tracked changes are not modeled as a high-level document rewrite. Instead, the design uses unpack-edit-repack XML manipulation so the system can insert tracked changes and comments in a way closer to native Word behavior.

## Repository Layout

The current repository centers on these locations:

```text
.
+-- .claude/
|   +-- agents/
|   +-- skills/
|   `-- settings.json
+-- contract-review/
|   `-- library/
|       +-- indexes/
|       `-- policies/
+-- docs/
+-- CLAUDE.md
+-- contract-review-agent-design.md
+-- package.json
`-- README.md
```

Important subtrees:

- `.claude/skills/doc-parser/`: normalization, fingerprinting, and file format detection
- `.claude/skills/index-manager/`: index build, query, and supersession helpers
- `.claude/skills/metadata-validator/`: manifest, package, and privilege-leak validation
- `.claude/skills/docx-redliner/`: clause mapping, redline application, comment insertion, and internal comment stripping
- `.claude/skills/report-compiler/`: DOCX report generation
- `.claude/skills/pipeline-state/`: save, load, and round diff helpers
- `contract-review/library/policies/`: behavior and retrieval configuration
- `contract-review/library/indexes/`: seed index files for documents, clauses, terms, retrieval mapping, and supersession

## Prerequisites

The implementation notes in this repository currently assume:

- Python 3.14+ for the helper scripts
- Node.js 24+ for the DOCX report compilers
- `PyYAML` for YAML-backed Python scripts
- `docx` for report generation

Optional tools:

- `pdftotext`, `pymupdf`, or `pypdf` for richer PDF support
- `pandoc` for enhanced DOCX conversion paths

## Setup

Install the declared and implied dependencies:

```bash
npm install
python -m pip install pyyaml
```

Then open the repository in Claude Code and use it as a Claude Code project rather than as a generic shell-only program.

## Recommended Starting Sequence

1. Review [`contract-review-agent-design.md`](./contract-review-agent-design.md) for the target workflows and artifact model.
2. Review [`CLAUDE.md`](./CLAUDE.md) for routing, safety rules, and folder access assumptions.
3. Adjust the policy files under [`contract-review/library/policies`](./contract-review/library/policies) to reflect your contract families, clause taxonomy, approval rules, metadata schema, and review posture.
4. Place source assets into the library intake path expected by your ingestion workflow.
5. Run an ingestion pass before attempting library-backed review.

## Typical Usage In Claude Code

Examples of intended usage:

```text
/ingest
/review
/rereview
/library search nda
```

Natural language requests are also part of the design, for example:

```text
Review this SaaS agreement in moderate mode.
Ingest the template I just added to the library.
Re-review round 2 against the prior draft.
```

## Policy Surfaces You Will Customize

The policy files under `contract-review/library/policies/` are central to the system's behavior:

- `contract-families.yaml`: supported agreement families and routing taxonomy
- `clause-taxonomy.yaml`: clause types used for segmentation and retrieval
- `metadata-schema.yaml`: required metadata structure
- `approval-rules.yaml`: approval gates and auto-approval behavior
- `retrieval-priority.yaml`: ordering of preferred sources during retrieval
- `review-mode.yaml`: strictness, tolerance, and comment/redline scope

## Outputs Defined By The Design

The target architecture produces artifacts such as:

- internal redlined DOCX
- external-clean redlined DOCX with internal comments stripped
- review report DOCX
- delta report DOCX
- machine-readable review JSON
- ingestion result JSON
- refreshed index JSON files

Some of these outputs are already supported by helper scripts in the repository, while others depend on how completely the surrounding Claude Code workflow has been wired together in your local environment.

## Current Gaps To Be Aware Of

- `package.json` only declares the `docx` dependency and does not expose the full workflow as npm commands.
- There is no top-level automated test suite configured yet.
- The design document is broader than the current repository snapshot, so not every roadmap feature should be assumed turnkey.
- The main operational surface is Claude Code orchestration plus local filesystem conventions, not a standalone application server.

## Roadmap Alignment

The design document breaks implementation into three phases:

- `v1-alpha`: ingestion, library management, report-oriented review, indexes, and resumability
- `v1-beta`: DOCX redlines/comments, clean export, and re-review lifecycle
- `v2`: drafting, deeper negotiation support, and more advanced retrieval

Use that phasing to decide whether a missing feature is a bug, an integration gap, or simply not in scope for the current state of the project.

## Reference Documents

- [`contract-review-agent-design.md`](./contract-review-agent-design.md): target architecture, workflows, folder structure, and roadmap
- [`CLAUDE.md`](./CLAUDE.md): orchestrator behavior and safety rules
- [`docs/implementation-notes.md`](./docs/implementation-notes.md): repository implementation notes

## License

This repository is licensed under the MIT License. See [`LICENSE`](./LICENSE).

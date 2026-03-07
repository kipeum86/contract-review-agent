# How to Use

> **Stuck on any step?** Ask Claude Code directly in the terminal, or paste a screenshot into any LLM — they are usually great at walking you through it.

## Environment

This project is built and tested in the following environment:

| Component | Detail |
|-----------|--------|
| Editor | **VS Code** |
| AI Interface | **Claude Code** (Anthropic's CLI for Claude, running in VS Code's integrated terminal) |
| OS | Windows 11 / macOS |
| Shell | Bash (Git Bash on Windows, default Terminal on macOS) |

Claude Code runs as an interactive agent inside your terminal. You give it natural-language instructions or slash commands, and it reads/writes files, runs scripts, and coordinates sub-agents — all within your local project directory.

> If you are not using Claude Code, the slash commands (`/ingest`, `/contract-review`, etc.) won't work directly. You would need to adapt the prompts for your own AI setup.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Claude Code** | Latest | [Installation guide](https://docs.anthropic.com/en/docs/claude-code) |
| **Python** | 3.14+ | Required for parsing/generation scripts |
| **Node.js** | 24+ | Required for project tooling |
| **PyYAML** | Latest | `pip install pyyaml` |

Optional dependencies:

| Package | Purpose |
|---------|---------|
| `pymupdf` or `pypdf` | PDF file support |
| `pandoc` | Enhanced DOCX conversion |

---

## Installation

```bash
git clone https://github.com/kipeum86/contract-review-agent.git
cd contract-review-agent
npm install
python -m pip install pyyaml
```

---

## Step-by-Step Setup

### 1. Customize Policies to Your Practice

The policy files in [`contract-review/library/policies/`](../contract-review/library/policies/) control how the agent classifies and reviews contracts. They ship with broad defaults covering 27 contract families, but you should tailor them to your practice area.

In the Claude Code terminal, just ask:

```text
Rewrite the policy files to match the contract types I work with.

Contract types I handle:
- NDA, license, IP assignment, content distribution, game development, ...
```

Claude Code will rewrite all six policy files (contract families, clause taxonomy, review modes, retrieval rules, etc.) in one pass. You can also edit the YAML files manually — see [Policy Files](#policy-files) below.

> **Tip — Not sure how to configure policies yet?** Skip to Step 2 first. Ingest your house templates, then come back and ask Claude Code to customize the policies based on the ingested contracts:
>
> ```text
> ingest된 계약서 유형에 맞게 policies파일 수정해줘.
> Rewrite policies to match the contract types already in my library.
> ```
>
> This is often easier than writing policy specs from scratch — let your actual contracts drive the configuration.

### 2. Seed Your Library

Drop your house templates and reference contracts into [`contract-review/library/inbox/raw/`](../contract-review/library/inbox/raw/), then type in the Claude Code terminal:

```text
/ingest
```

| Guideline | Detail |
|-----------|--------|
| Volume | **50 documents or fewer** for initial setup. Add more anytime. |
| Formats | DOCX, PDF, Markdown |
| Structure | One agreement per file |
| Privacy | All files stay on your local machine — never uploaded or shared anywhere |

Templates and precedents are **auto-approved** by default. Playbooks and comment banks require human confirmation. See [`approval-rules.yaml`](../contract-review/library/policies/approval-rules.yaml).

### 3. Review a Contract

Drop the contract you want reviewed into the [`input/`](../input/) folder at the project root, then type:

```text
/contract-review
```

Results (redlined DOCX, analysis report, etc.) are saved to the [`output/`](../output/) folder.

Both `input/` and `output/` are excluded from version control — your contract files never leave your local PC.

Natural language also works:

```text
이 SaaS 계약서 moderate 모드로 검토해줘.
Review this NDA strictly.
```

### 4. Re-review a Revised Draft

When the counterparty sends back a revised version, drop it into `input/` and type:

```text
/rereview
```

The agent compares the new draft against the prior review round and produces a **delta report** highlighting what changed, what was accepted, and what new issues appeared.

### 5. Other Commands

| Command | What it does |
|---------|-------------|
| `/library` | Search, list, show, deprecate, or archive library assets |
| `/export-clean` | Strip `[INTERNAL]` comments from a redlined DOCX (safe for counterparty) |
| `/resume` | Resume an interrupted pipeline from where it left off |
| `/draft` | Draft a new contract *(roadmap — v2)* |

You can also use natural language — the orchestrator routes to the correct workflow automatically.

---

## Typical Workflow in VS Code

Here is what a typical session looks like:

1. **Open the project** in VS Code.
2. **Open the integrated terminal** (`Ctrl+`` ` or `View > Terminal`).
3. **Start Claude Code** by typing `claude` in the terminal.
4. **Give instructions** — either slash commands or natural language, in English or Korean.
5. **Watch Claude Code work** — it reads files, runs scripts, writes outputs, and reports progress in the terminal.
6. **Review the results** — open the output files in VS Code to inspect redlines, reports, and analysis.
7. **Iterate** — ask follow-up questions, request changes, or proceed to the next step.

The entire interaction happens inside the VS Code terminal. There is no separate web UI or browser window.

---

## Policy Files

Six YAML files under [`contract-review/library/policies/`](../contract-review/library/policies/) control the agent's behavior:

| File | Controls | Edit? |
|------|----------|-------|
| `contract-families.yaml` | Supported agreement types | **Yes** |
| `clause-taxonomy.yaml` | Clause classification hierarchy | **Yes** |
| `review-mode.yaml` | Strict / moderate / loose review settings | **Yes** |
| `approval-rules.yaml` | Auto-approval toggle and per-asset-type rules | **Yes** |
| `retrieval-priority.yaml` | Search ranking, affinity groups | Optional |
| `metadata-schema.yaml` | Metadata field definitions | Optional |

These are **read-only for the agent** — only you (or Claude Code at your request) edit them.

---

## Tips

- **Language**: The agent works in both English and Korean. It matches the language of your input.
- **Review modes**: Override the default (`moderate`) per review — say "엄격하게 검토해줘" or "do a loose review".
- **Pipeline resume**: If a review is interrupted (terminal closed, error, etc.), just type `/resume` to pick up where it left off.
- **Audience firewall**: Internal strategy comments (`[INTERNAL]`) are never included in external-facing output. Use `/export-clean` to produce a version safe for the counterparty.

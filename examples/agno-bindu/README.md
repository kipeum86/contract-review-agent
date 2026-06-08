# Exposing `contract-review-agent` as a network-addressable Bindu agent

This directory wraps the contract-review methodology from this project as an
[agno](https://github.com/agno-agi/agno) agent and serves it over the
[Bindu](https://github.com/GetBindu/Bindu) **Agent-to-Agent (A2A)** protocol — a
DID-identified HTTP endpoint that other agents (or a curl one-liner) can send a
contract to and get back a clause-by-clause review. It does this by **loading this
repository's own Claude Code skills into agno at runtime** — the agent reads your
`.claude/skills/` (the four-lens review guide, the clause segmenter, the review-mode
policy) and reasons with them, rather than reimplementing any of it.

> [!NOTE]
> **Community-built example.** Not affiliated with or endorsed by the
> `contract-review-agent` maintainers. The project's skills and policies are the
> source of truth and remain under their own Apache-2.0 LICENSE; this directory is
> example glue for one way to drive a *subset* of them over a network protocol.

Contributed by the team at [Bindu](https://github.com/GetBindu/Bindu). This agent is
one entry in the Bindu example showcase; the real review intelligence belongs to the
`contract-review-agent` project, which this example loads in place and links back to
as the canonical source.

## Maintenance

The review methodology, skills, and policies under `.claude/` and
`contract-review/library/policies.default/` are maintained by the
`contract-review-agent` authors — file methodology or policy issues **there**.

For issues with *this example* (the Bindu/agno glue, the loader, the prompt, this
README), open an issue on [Bindu](https://github.com/GetBindu/Bindu) and tag it
`[contract-review example]`, or reach the Bindu team on Discord.

## What the example does

You paste a contract (or a single clause) as text; the agent returns:

- the **contract family** (classified against the project's 29-family taxonomy) and
  the **review mode** in effect (`strict` / `moderate` / `loose`, default `moderate`,
  overridable in plain language);
- a **clause-by-clause table** — clause · risk grade (Critical → Acceptable) · the
  issue · a concrete redline suggestion;
- **comments split by audience** — `[EXTERNAL]` (safe to send to the counterparty)
  and `[INTERNAL]` (your strategy, leverage, and fallback notes), with the project's
  audience-firewall rule keeping strategy out of the external set;
- **negotiation recommendations** — what to push on first, and acceptable landing
  zones.

The risk grading, the four-lens analysis framework, the review-mode scopes, and the
audience-firewall rules are **not** baked into this example — the agent loads them
from the project's skills on each run (see below). It answers in the contract's
language (it will review a Korean clause in Korean, citing Korean statutes).

This is a **stateless, text-in** surface. It deliberately does **not** drive the
project's full local pipeline — no house-library retrieval, no tracked-change DOCX
output, no ingestion, hooks, or pipeline-state. Those remain the job of the full
`contract-review-agent` Claude Code application. See **Scope** at the bottom.

## The libraries it uses

- **[agno](https://github.com/agno-agi/agno)** — the agent loop: it makes the model
  call, decides which skill/tool to invoke, and runs the conversation. agno's
  **Skills** feature is what lets it consume this repo's `.claude/skills/` directly.
- **[Bindu](https://github.com/GetBindu/Bindu)** — exposes the agno agent over A2A:
  a DID identity, a public agent card, and the JSON-RPC `message/send` / `tasks/get`
  endpoints.

## How the skills loading works

This project is a **Claude Code application** — its capabilities live in
`.claude/skills/<name>/SKILL.md` (instructions), `references/` (methodology docs like
`review-guide.md`), and `scripts/` (deterministic Python helpers). agno can consume
exactly that layout via [Agent Skills](https://docs.agno.com/skills/loading-skills),
which gives the agent three tools — `get_skill_instructions`, `get_skill_reference`,
and `get_skill_script` — and lists the available skills in its system prompt so it
loads detail only when it needs it (progressive disclosure).

There is one mismatch: most of this repo's `SKILL.md` files have **no YAML
frontmatter**, which agno's default `LocalSkills` loader requires. Rather than modify
any upstream file, [`skills_loader.py`](skills_loader.py) ships a tiny
`ClaudeCodeSkills` adapter that loads them with validation off (the folder name
becomes the skill name) and backfills the one-line description from the text under
each skill's H1. Crucially, `source_path` points **straight at this repo's skill
folders**, so their real `references/` and `scripts/` are read (and could be executed)
in place — nothing is copied, generated, or modified.

For this stateless review surface the example loads the two **text-native methodology
skills**:

| Skill loaded | What the agent gets from it |
|---|---|
| `review-domain-knowledge` | Risk-grading criteria + the four-lens framework (`references/review-guide.md`), the audience-firewall rules (`references/audience-firewall.md`), review-mode scoping, comment-generation rules. |
| `clause-segmenter` | How to segment a contract into clause-level units and classify each (`references/segmentation-guide.md`). |

It also exposes one small read-only tool, `load_policy(name)`, over the project's own
`contract-review/library/policies.default/` YAMLs — `review-mode` (the strict/
moderate/loose scopes), `contract-families` (the 29 families), and `clause-taxonomy`.

The project's other skills — `doc-parser`, `docx-redliner`, `report-compiler`,
`index-manager`, `metadata-validator`, `pipeline-state`, `ingest` — drive the full
*local* DOCX pipeline (files on disk, Node, the house library) and are out of scope
for a stateless text endpoint. You can load more by editing `DEFAULT_SKILLS` in
`skills_loader.py`.

## Setup

All commands use [`uv`](https://docs.astral.sh/uv/). Run them from the repo root.

```bash
# 1. A virtual environment for the example.
uv venv && source .venv/bin/activate

# 2. The example's own dependencies. The project's skills are read straight from
#    .claude/skills/ in this repo, so there is no upstream package to install.
uv pip install -r examples/agno-bindu/requirements.txt

# 3. Your model key.
cp examples/agno-bindu/.env.example examples/agno-bindu/.env
#    then edit examples/agno-bindu/.env and set OPENROUTER_API_KEY=sk-or-...
```

The agent finds this repo (its `.claude/skills/` and policy files) automatically — it
sits at `examples/agno-bindu/`, two levels down. Running it from elsewhere? Set
`CONTRACT_REVIEW_REPO=/path/to/contract-review-agent` in the `.env`.

## Run the CLI (one-shot, local)

The fastest way to see it work — no server:

```bash
uv run python examples/agno-bindu/cli.py "Review this clause as the customer: \
'Provider may terminate at any time for any reason on 30 days notice. Customer may \
terminate only for Provider's uncured material breach.'"
```

Abbreviated output (the agent first loads the skills, then reviews):

```markdown
## Clause Review — Termination
Contract family: Services/SaaS · Review mode: moderate · Your role: Customer

| Clause | Risk | Issue | Redline Suggestion |
|--------|------|-------|--------------------|
| Termination | 🔴 Critical | Asymmetry: Provider may exit "for any reason" on 30 days'
  notice while you are locked in absent the Provider's *uncured material* breach — a
  far higher bar. No reciprocal convenience right. | "Either party may terminate for
  convenience on 90 days' written notice; either party may terminate for the other's
  material breach uncured after 30 days' written notice." |

[INTERNAL] Must-have. With moderate leverage, push for a mutual convenience right…
This review is informational and not legal advice.
```

## Run the A2A service

```bash
uv run python examples/agno-bindu/bindu_agent.py
```

This starts the agent on `http://localhost:3773` with:

- `GET /.well-known/agent.json` — the agent card. The DID is published under
  `capabilities.extensions[].uri` as `did:bindu:…`.
- `GET /.well-known/did.json` — the DID document.
- `GET /health` — health payload (`health: healthy`, `task_manager_running: true`).
- `POST /` — JSON-RPC 2.0: `message/send` (returns a task id, state `submitted`) and
  `tasks/get` (poll until `completed`).

## Try it out

`message/send` is asynchronous: it returns a task id, and you poll `tasks/get` until
the task is `completed`. The JSON-RPC `id` and the three message ids must be real
UUIDs. This self-contained snippet does the whole round-trip:

```bash
BASE=http://localhost:3773
RPC_ID=$(uuidgen); MSG_ID=$(uuidgen); CTX_ID=$(uuidgen); TASK_ID=$(uuidgen)
Q="Review this mutual NDA in loose mode: 'The receiving party shall protect \
Confidential Information using the same degree of care it uses for its own. \
Obligations survive for two (2) years. Either party may assign without consent.'"

# 1. Send the contract text as a TEXT part.
curl -s -X POST "$BASE" -H 'content-type: application/json' -d "{
  \"jsonrpc\":\"2.0\",\"id\":\"$RPC_ID\",\"method\":\"message/send\",
  \"params\":{
    \"configuration\":{\"acceptedOutputModes\":[\"text/plain\"]},
    \"message\":{\"role\":\"user\",\"messageId\":\"$MSG_ID\",\"contextId\":\"$CTX_ID\",
      \"taskId\":\"$TASK_ID\",\"kind\":\"message\",
      \"parts\":[{\"kind\":\"text\",\"text\":$(printf '%s' "$Q" | jq -Rs .)}]}
  }
}" | jq -r '.result.status.state'   # -> submitted

# 2. Poll until completed, then print the review.
curl -s -X POST "$BASE" -H 'content-type: application/json' -d "{
  \"jsonrpc\":\"2.0\",\"id\":\"$(uuidgen)\",\"method\":\"tasks/get\",
  \"params\":{\"taskId\":\"$TASK_ID\"}
}" | jq -r '.result.artifacts[0].parts[0].text'
```

> [!IMPORTANT]
> **Send contract text, not files.** A2A file-part attachments are unreliable across
> the current Bindu versions, so this example takes the contract as a `text` part.
> Extract the text from your PDF/DOCX on your side and paste it in.

## Network exposure & dependencies

- **Local by default.** `deployment.expose` is `false`. Setting `BINDU_EXPOSE=true`
  asks Bindu to open an FRP reverse tunnel that makes this endpoint reachable on the
  public internet. That endpoint is **unauthenticated** and your `OPENROUTER_API_KEY`
  is on the billing path — leave it off unless you mean it.
- **Opt-in dependencies.** Everything extra lives in
  [`requirements.txt`](requirements.txt) (`bindu`, `agno`, `openai`, `python-dotenv`,
  `rich`) and is installed only into the example's virtualenv. No upstream file is
  modified and no upstream package is installed — the skills are read in place.
- **Not legal advice.** This is an informational example. Final legal judgment stays
  with a qualified human.

## Scope — what this is and isn't

This example is the project's review *methodology*, made callable over a network. It
loads the real review skills and reasons with them on contract text. It is **not** a
replacement for the full `contract-review-agent` application: the house-library
retrieval, the tracked-change DOCX redlines and reports, ingestion, the audience-
firewall validation scripts, and pipeline-state/resume all live in the Claude Code
app and operate on your local filesystem. Use the full project for those; use this
when you want a quick, network-addressable clause review grounded in the same rules.

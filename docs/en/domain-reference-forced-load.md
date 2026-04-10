# Domain Reference Forced-Load Architecture

> **Status**: Shipped (2026-04-10). Commits `c5a4a3e`..`a595f44` on `main`.
>
> This is a concise English overview. The authoritative design document (with
> full incident history, v1→v2→v2.1 patch log, open questions, failure modes,
> and test procedures) is in Korean at
> [`docs/ko/domain-reference-forced-load.md`](../ko/domain-reference-forced-load.md).

---

## 1. Why this exists

On 2026-04-09, the review-agent was caught generating an entire contract review
**without ever reading `review-guide.md`**. When asked directly, it admitted:

> "I did not consider it. I never opened the file. The review was based entirely
> on pretrained knowledge (FIDIC Silver Book, international EPC market practice)
> and the contract text."

The user's customized risk baselines (Common Law Contract Risk Reference, EPC
block, E&W/US/SG jurisdiction flags) had been written into `review-guide.md` but
**were never injected into the LLM's context** during analysis. Every prior
review on this branch was structurally unable to use the reference file.

The root cause is not a bug — it is the absence of a mechanism. Instructing the
LLM to "apply the four-lens framework from `review-guide.md`" is satisfied by
pretrained knowledge of those concepts. Nothing forces the file content into
the working context. This architecture fixes that.

## 2. Design principle

**Don't ask the LLM to read the file. Put the file in its context.**

The LLM cannot cite what it cannot see. If `review-guide.md` content is physically
present in the context window as a Bash tool result, the LLM can only analyze
against it (or refuse) — it cannot substitute training data without visibly
contradicting the block in front of it.

The mechanism:

1. **Hook** (`.claude/hooks/inject-domain-references.sh`) detects review
   workflow keywords in the user prompt and injects a `[BLOCKING PRECONDITION]`
   instruction via `additionalContext`: *"Before any other action, run
   `bash .claude/scripts/load-domain-references.sh review`."*

2. **Loader** (`.claude/scripts/load-domain-references.sh`) cats the reference
   files to stdout with `BEGIN AUTO-INJECTED DOMAIN REFERENCES` markers, and
   writes a trace JSON with `byte_size + sha256 + canary heading`.

3. **LLM Bash call** delivers the loader stdout back to the LLM as a Bash
   tool result. Bash tool output has no size cap (unlike the hook's 10K
   `additionalContext` limit, which was the reason v1 of this design failed
   feasibility review).

## 3. Three-layer defense in depth

If any one layer fails silently, the next layer catches it.

| # | Layer | Where | When it fires |
|---|---|---|---|
| 1 | **Hook injection** | `.claude/settings.json` → `UserPromptSubmit` hook → `inject-domain-references.sh` | Every user prompt matching review/draft/ingest keywords (primary path) |
| 2 | **Agent filesystem fallback** | `review-agent/AGENT.md` Pre-Pipeline 0 | Checks `contract-review/library/runs/sessions/*/loaded.json` freshness; runs the loader itself if missing or stale (>300s). Not LLM self-reporting — actual `ls -t` + `test -f` |
| 3 | **Root dispatch proactive load** | `CLAUDE.md` → "Baseline Reference Load — Root Agent Dispatch Protocol" | Before dispatching `review-agent` as a sub-agent, the root orchestrator runs the loader. Catches the case where Claude Code does not re-fire hooks on sub-agent dispatch |

## 4. Forensic trace (hallucination-proof)

Every loader invocation writes:

```json
{
  "workflow": "review",
  "loader_version": "2.1",
  "source": "hook",
  "loaded_at": "2026-04-10T10:23:45Z",
  "session_id": "20260410T102345Z-12345-6789",
  "files_loaded": [
    {
      "name": "review-guide.md",
      "byte_size": 25018,
      "sha256_short": "a3f2e1c9",
      "last_section_heading": "### JSON Field Mapping for compile-report.js"
    },
    ...
  ]
}
```

to `contract-review/library/runs/sessions/{session_id}/loaded.json`. Step 1.5
of `review-agent/AGENT.md` copies this file into
`matters/{id}/round_{N}/working/baseline-context/loaded.json`.

At Step 10, **`compile-report.js` reads the trace JSON directly and appends
a `Baselines applied: ...` line to `data.executive_summary.recommendation`** —
the LLM never writes this line. Because the line contains `sha256_short` and
`last_section_heading` (the canary) read from the file, the LLM cannot
fabricate a convincing trace line without actually running the loader.

If `loaded.json` is missing or malformed, the script appends
`⚠️ REVIEW INVALID — baseline-context/loaded.json missing...` instead. The
final DOCX carries this warning visibly.

### Backward compatibility

`compile-report.js` accepts the matter working directory as an **optional 3rd
argument**. When omitted (v1 2-arg invocation), `injectBaselineTrace()` is a
no-op and the output DOCX is byte-identical to v1 behavior. Re-compiling a
pre-v2.1 review data file will **not** introduce a false warning. This is
explicitly tested in Test 4b variant 4.

## 5. What the user sees

A single line at the end of the Executive Summary `Recommendation` section:

> Baselines applied: review-guide.md (25018 bytes, sha256: a3f2e1c9,
> canary: "### Other / Amendments / Side Letters"), audience-firewall.md
> (4046 bytes, sha256: b8d1f4e2, canary: "### Batch Validation"). Loaded at
> 2026-04-10T10:23:45Z via hook.

If this line is absent or replaced with a `⚠️ REVIEW INVALID` warning, the
review is not trustworthy and should be re-run.

## 6. Workflow coverage

| Workflow | Slash command | Hook mode | Rationale |
|---|---|---|---|
| Contract Review | `/contract-review`, `/rereview` | **BLOCKING PRECONDITION** | The 2026-04-09 incident was in this workflow. Maximum enforcement. |
| Drafting | `/draft` | HINT only | No incident observed. Lighter enforcement to avoid over-engineering an unproven path. |
| Ingestion | `/ingest` | HINT (preserves legacy `[Hook]` format) | Existing ingest hook worked for ~1 year. The new unified hook absorbs its keyword set (Test 0.5 regression verified) and adds an optional loader nudge. |
| Library / Export | `/library`, `/export-clean` | No injection | No reference files needed. |

## 7. Prerequisites

- **`jq`** — parses hook stdin JSON, builds `additionalContext` JSON, writes
  trace files. Install: `brew install jq` (macOS) · `apt-get install jq`
  (Linux). **If absent, the hook logs an error to stderr and falls through
  to an empty injection — reviews silently regress to pretrained knowledge
  only.**
- **`shasum` or `sha256sum`** — preinstalled on macOS and most Linux distros.
  Used for the canary in the trace JSON.

## 8. Open questions (still under observation)

These cannot be answered from a script test; they require real Claude Code
sessions with actual sub-agent dispatch and user interaction:

1. **Does the `UserPromptSubmit` hook re-fire when the root agent dispatches
   `review-agent` as a sub-agent?** Claude Code's official documentation is
   silent. The `source` field in `loaded.json` reveals which path fired
   (`hook` / `agent-prepipe` / `root-dispatch`). Run 10 sessions, observe the
   distribution.

2. **Does the LLM actually obey the `[BLOCKING PRECONDITION]` instruction?**
   Target is ≥9/10 sessions running the loader as the first tool call,
   before any `AskUserQuestion`. If below that threshold, the hook instruction
   language needs strengthening or the design needs rethinking.

3. **Does the hook fire in plan mode?** Unknown.

4. **Do drafting and ingest workflows actually reproduce the incident in
   practice?** If yes, promote their lightweight HINT to BLOCKING. If no,
   leave them as-is.

## 9. Rollback

If anything goes wrong, roll back in layers:

```bash
# Revert just the hook activation (everything else stays dormant):
git revert a595f44

# Full rollback of the v2.1 implementation:
git revert a595f44 d27137c 10733cd c5a4a3e 20d725c
```

Commits 20d725c through 10733cd are inert on their own (the loader and
compile-report.js changes are dormant until the hook is registered in
`a595f44`), so reverting only the activation commit is sufficient for a
safe rollback.

## 10. Further reading

- Full architecture document (Korean, authoritative):
  [`docs/ko/domain-reference-forced-load.md`](../ko/domain-reference-forced-load.md)
- Incident session log (local-only, not in git):
  `logs/session-2026-04-09-common-law-conversion-and-forced-load-architecture.md`
- Loader script: [`.claude/scripts/load-domain-references.sh`](../../.claude/scripts/load-domain-references.sh)
- Hook script: [`.claude/hooks/inject-domain-references.sh`](../../.claude/hooks/inject-domain-references.sh)
- Agent integration: [`.claude/agents/review-agent/AGENT.md`](../../.claude/agents/review-agent/AGENT.md)
  (Pre-Pipeline 0, Step 1.5, Step 5.5, Step 10)
- Compiler change: [`.claude/skills/report-compiler/scripts/compile-report.js`](../../.claude/skills/report-compiler/scripts/compile-report.js)
  (`injectBaselineTrace()`)

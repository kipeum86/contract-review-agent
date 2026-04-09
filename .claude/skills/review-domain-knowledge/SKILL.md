# review-domain-knowledge Skill

Domain knowledge for contract review and drafting: classification, analysis, comment generation, and contract generation.

## References

Detailed domain knowledge is in the `references/` directory:
- `domain-policy.md` — Folder schema, ingestion policy, document lifecycle
- `review-guide.md` — Review judgment criteria, risk grading, analysis methodology
- `audience-firewall.md` — External/internal content separation rules
- `drafting-guide.md` — Contract generation checklists, Korean law baselines, drafting rules

## CRITICAL: Reference Files Are Auto-Loaded via Forced-Load Protocol (v2.1)

The reference files above are **not background context** you should recall from training. They are the authoritative source of user-customized judgment criteria, risk baselines, and firewall rules. They WILL diverge from your pretrained knowledge.

**For the review workflow**, reference files are loaded via the Domain Reference Forced-Load Architecture:

1. **Hook path** (primary): `.claude/hooks/inject-domain-references.sh` detects review workflow keywords in the user prompt and injects a `[BLOCKING PRECONDITION]` instruction telling the LLM to run `bash .claude/scripts/load-domain-references.sh review` as its first action. The loader cats the files into the Bash tool result, which has no size cap.

2. **AGENT.md fallback** (secondary): `review-agent/AGENT.md` Pre-Pipeline 0 runs a filesystem check (`ls -t`) on `contract-review/library/runs/sessions/*/loaded.json` and, if missing or stale, runs the loader itself. This catches cases where the hook did not fire (e.g., sub-agent dispatch).

3. **Forensic trace**: Every loader invocation writes `loaded.json` (byte_size + sha256 + canary heading). `compile-report.js` reads this at Step 10 and appends a `Baselines applied: ...` line to the Executive Summary. If the trace is missing, a `⚠️ REVIEW INVALID` warning is appended instead.

**Do not cite the four-lens framework, Common Law baselines, jurisdiction flags, or EPC block from training.** Cite them only from the `<!-- BEGIN AUTO-INJECTED DOMAIN REFERENCES -->` block in your current context. This block is the result of the loader script running — its absence means you must not proceed with analysis.

Full architecture: `output/Domain-Reference-강제로드-아키텍처-기획-v2.md`. Incident: `logs/session-2026-04-09-common-law-conversion-and-forced-load-architecture.md`.

## Safety Utilities

- `scripts/validate-audience-firewall.py` — Batch-validates `[EXTERNAL]` comments and writes `working/comments/firewall-log.json`

## Classification (WF1 Step 4, WF2 Step 2)

When classifying a document, determine:
1. `doc_class`: template | precedent | playbook | comment_bank | review_target
2. `contract_family`: from `contract-families.yaml`
3. `subtype`: from the family's subtypes
4. `paper_role`: house | counterparty | neutral | internal
5. `jurisdiction`: primary jurisdiction
6. `governing_law`: governing law
7. `language`: primary document language (ISO 639-1)

Apply sidecar values first when available. Infer only missing fields.
Assign confidence: high | medium | low. Provide ≥ 3 reasoning sentences.

## Comparative Analysis (WF2 Step 6)

For each target clause matched to a library clause:
1. Identify divergences from house position
2. Assign risk grade: Critical | High | Medium | Low | Acceptable
3. Determine playbook tier: preferred | acceptable | fallback | prohibited
4. Assess whether modification is necessary

Apply review mode (from `review-mode.yaml`):
- **strict**: flag all deviations, only preferred is acceptable
- **moderate**: flag Critical+High, preferred+acceptable tolerated
- **loose**: flag Critical only, fallback is tolerated

When no playbook exists, use matched template clause as baseline and set `playbook_missing: true`.

## Comment Generation (WF2 Step 7)

### External Comments (`[EXTERNAL]`)
- Only for Critical and High risk clauses (expanded by review mode)
- Reuse from `comment-bank/external` when available
- **MUST NOT** contain internal strategy, fallback positions, or leverage info
- Must pass audience firewall check (see `audience-firewall.md`)
- Run `scripts/validate-audience-firewall.py` on the final comment set before DOCX generation

### Internal Notes (`[INTERNAL]`)
- For any clause with substantive observations
- Include reasoning, strategy notes, fallback positions
- Reference `comment-bank/internal` when available

### Redline Suggestions
- Propose alternative clause text from the fallback ladder
- Scope governed by review mode
- Text must be in the contract's original language

## Drafting (WF5 Steps 5-6)

When generating contracts using the drafting workflow:
1. **Checklist application**: Use contract-family-specific checklists from `drafting-guide.md` to ensure completeness
2. **Statutory compliance**: For Korean-law contracts, verify against Korean Law Statutory Baselines in `drafting-guide.md`
3. **Tier selection**: Apply leverage-based clause selection (preferred / acceptable / fallback) per `drafting-guide.md`
4. **Self-review**: Run five-point checklist and four-lens framework from `drafting-guide.md`
5. **Generation rules**: Follow defined terms, cross-references, numbering, and placeholder rules in `drafting-guide.md`

## Review Mode Definitions

| Mode | Redline Scope | Acceptable Tier | Comments For |
|------|--------------|-----------------|-------------|
| strict | All deviations | preferred only | All levels |
| moderate | Critical+High | preferred+acceptable | Critical+High+Medium |
| loose | Critical only | preferred+acceptable+fallback | Critical+High |

## Language Policy

| Content | Language |
|---------|----------|
| Redline text | Contract's original language |
| `[EXTERNAL]` comments | Contract's original language |
| `[INTERNAL]` comments | Report language |
| Analysis report | User-specified or prompt language |
| Terminal output | Prompt language |

## Matter Context

Accept deal context as natural language or YAML. Structure into `matter-context.yaml`:

```yaml
party_role: customer
counterparty: "Acme Software Inc."
contract_type: saas_subscription
leverage: moderate
priority_areas:
  - limitation_of_liability
  - data_protection
notes: "Standard deal"
review_mode: moderate
language: ko
```

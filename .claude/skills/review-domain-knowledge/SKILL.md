# review-domain-knowledge Skill

Domain knowledge for contract review: classification, analysis, and comment generation.

## References

Detailed domain knowledge is in the `references/` directory:
- `domain-policy.md` — Folder schema, ingestion policy, document lifecycle
- `review-guide.md` — Review judgment criteria, risk grading, analysis methodology
- `audience-firewall.md` — External/internal content separation rules

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

### Internal Notes (`[INTERNAL]`)
- For any clause with substantive observations
- Include reasoning, strategy notes, fallback positions
- Reference `comment-bank/internal` when available

### Redline Suggestions
- Propose alternative clause text from the fallback ladder
- Scope governed by review mode
- Text must be in the contract's original language

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

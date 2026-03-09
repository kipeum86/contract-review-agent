# Contract Review Judgment Guide

## Risk Grading Criteria

### Critical
The clause creates an **unacceptable** legal or commercial exposure. Immediate attention required.

Examples:
- Unlimited liability with no cap
- Unilateral termination rights without cure period
- Broad IP assignment without compensation
- Indemnification for counterparty's own negligence
- Prohibited position per playbook
- Governing law in hostile jurisdiction with no fallback

### High
The clause contains **significant** deviations from house position. Should be negotiated.

Examples:
- Liability cap set unreasonably low relative to contract value
- Overly broad non-compete or non-solicitation
- Missing limitation of consequential damages
- Unilateral amendment rights
- Data processing without adequate security requirements
- Auto-renewal without opt-out mechanism

### Medium
The clause contains **notable** deviations that may be acceptable depending on context.

Examples:
- Slightly narrower confidentiality exceptions than house standard
- Notice period shorter than preferred but within industry norms
- Force majeure clause narrower than house template
- Payment terms longer than preferred
- Assignment restriction without change-of-control exception

### Low
The clause contains **minor** deviations that are generally acceptable.

Examples:
- Stylistic differences in boilerplate
- Notice address format variations
- Counterparts provision wording differences
- Slightly different severability formulation
- Minor variations in defined terms structure

### Acceptable
The clause is **substantially aligned** with house position or industry standard.

## Analysis Methodology

### Four-Lens Analysis Framework

Before grading any clause, apply all four lenses:

1. **Asymmetries** — Does this provision apply to one party differently than the other? Any right, obligation, remedy, or restriction that is unilateral or applies on materially different terms warrants scrutiny.

2. **Overbroad Qualifiers** — Are knowledge qualifiers, materiality thresholds, or carve-outs used in ways that hollow out protections the client should have? (e.g., "to the best of Seller's knowledge" on a rep that should be absolute; a "material breach" threshold that effectively voids any termination right)

3. **Missing Protections** — What standard provisions for this contract type are absent entirely? A missing clause can be more dangerous than a bad one. (e.g., no limitation of liability clause, no IP ownership provision, no data breach notification obligation)

4. **Structural Traps** — Do provisions that appear neutral individually combine with other clauses to produce a one-sided outcome? (e.g., a basket equal to the indemnification cap, making indemnification illusory; a cure period that starts running before written notice is received)

### Per-Clause Procedure

For each clause:

1. **Read** the target clause text completely
2. **Apply the four lenses** above — note any asymmetry, overbroad qualifier, missing protection, or structural trap
3. **Compare** against the matched library clause (house position)
4. **Check** the playbook for this clause type (if available):
   - Is the clause within the preferred tier?
   - Does it match an acceptable alternative?
   - Has it fallen to fallback territory?
   - Does it hit a prohibited position?
5. **Assess** the risk in context:
   - What is the commercial impact?
   - What is the legal exposure?
   - Is this a standard market position?
   - What does the matter context suggest (leverage, priority areas)?
6. **Grade** the risk level
7. **Document** the reasoning using this structured format: `[deviation identified] → [legal/commercial impact] → [market standard reference] → [risk verdict]`

## Playbook Integration

When a playbook exists for the clause type:
- **preferred**: The ideal position. This is what we want.
- **acceptable**: We can live with this. No need to fight.
- **fallback**: Our bottom line. Accept only if necessary.
- **prohibited**: Never accept. If present, grade as Critical.

When no playbook exists:
- Use the matched template clause text as baseline
- Set `playbook_missing: true` in the analysis
- Apply general contract law principles for risk assessment

## Context-Sensitive Analysis

Matter context values from `matter-context.yaml` prescribe specific adjustments to default risk grading — they are not advisory.

### Leverage Rules

- **`leverage: high`**: For all `priority_areas` clause types, upgrade base risk by one tier (Medium → High, Low → Medium). For all other clauses, apply review mode at `strict` regardless of `review-mode.yaml` default.
- **`leverage: low`**: Restrict Must-have list to Critical only. Do not generate redlines for High items unless they are explicitly listed in `priority_areas`.
- **`leverage: moderate`**: Apply default review mode without adjustment.

### Priority Areas Rules

If a `clause_type` is in `priority_areas`:
- `leverage: high` → treat as High even if base grade is Medium or Low; always include in Key Issues list
- `leverage: moderate` → treat as Medium even if base grade is Low; include in Key Issues list
- `leverage: low` → treat as Medium; include in Key Issues list even when operating in loose mode
- **Priority area items are always included in the Key Issues list regardless of review mode threshold.**

### Party Role Rules

- **`party_role: house`** (우리 측 초안): Focus on counterparty's proposed deviations from our draft. Asymmetries that favor us are acceptable by design; do not flag them.
- **`party_role: counterparty`** (상대방 초안): Apply full four-lens analysis. Default assumption is the draft is counterparty-favorable; scrutinize every asymmetry.
- **`party_role: neutral`** (공동 협상): Flag asymmetries in both directions with no default favorability assumption.
- **`party_role: internal`** (내부 문서): Apply criteria appropriate for internal policies; audience firewall rules do not apply.

## Redline Suggestion Rules

1. Redline text must be in the **contract's original language**
2. Draw from the fallback ladder when available
3. Make the minimum change necessary to bring the clause to an acceptable position
4. Preserve the counterparty's structure and numbering where possible
5. Never introduce new obligations not present in the original

## General Review Mode

When the library is empty:
- State clearly: "This review was performed in general review mode without house position comparison"
- Base analysis on general contract law principles only
- Focus on identifying one-sided provisions, missing protections, and ambiguities
- Omit house position comparison entirely
- Risk grading is still applicable — use market standards as the reference point

---

## Korean Contract Risk Reference

Use when reviewing Korean-law contracts or operating in general review mode. These reflect Korean statutory baselines and market practice as of 2026.

### Investment Contracts (투자 계약)

**SAFE / 조건부지분전환계약**
- No conversion mechanism, discount rate, or valuation cap → Critical (투자자 전환 이익 없음)
- No anti-dilution protection (가중평균 또는 완전희석 방식 미포함) → High
- No investor information rights → High

**SHA / 주주간계약**
- Drag-along right with no minimum threshold or founder carve-out → Critical
- Tag-along right absent for minority shareholders → High
- Information rights absent (financial statements, board minutes) → High
- Board seat or observer right unspecified for major investor (≥ 5%) → Medium

**주식인수계약 (SPA / SSA)**
- No MAC (Material Adverse Change) clause → High
- Indemnification cap below purchase price → High
- No disclosure schedule requirement for representations → Medium

### NDA / 비밀유지계약

- 비밀유지 기간 less than 2 years post-termination, or no fixed end date → Medium
- No mutual confidentiality obligation in bilateral NDA → Medium
- No return or destruction of materials obligation on termination → Low

### Service / SaaS 계약

- No liability cap (책임 한도 없음) → Critical
- No consequential damages exclusion → High
- Work product IP ownership (용역 결과물 귀속) unspecified → High
- No SLA or uptime commitment for SaaS → Medium

### Employment Contracts (근로계약)

- Salary below minimum wage (최저임금 미달) → Critical (근로기준법 위반)
- Working hours exceeding 52 hours/week without lawful overtime framework → Critical
- No retirement pay provision for employment ≥ 1 year (퇴직금 미적립) → Critical (근로기준법 제34조)
- Non-compete clause (경업금지) exceeding 2 years without separate compensation → High

### Data Protection (개인정보 보호법 / PIPA)

- Personal information collection without consent mechanism → Critical
- No purpose limitation clause (수집 목적 미특정) → High
- Third-party transfer without data subject consent framework → High
- Retention period unspecified → Medium
- No security measures obligation → High

---

## Executive Summary Template

When generating the Executive Summary for the analysis report (WF2 Step 10), always use this structure:

### Section 1 — Contract Overview (2–3 sentences)
- Contract type, parties, and principal transaction structure
- Contract language, jurisdiction, and governing law

### Section 2 — Overall Risk Assessment
- Overall risk level: **Critical** | **High** | **Medium** | **Low**
  - Critical: one or more Critical-grade issues present
  - High: no Critical issues, but High-grade issues present
  - Medium / Low: graded accordingly
- Risk distribution table:

| Risk Level | Count |
|------------|-------|
| 🔴 Critical | N |
| 🟠 High | N |
| 🟡 Medium | N |
| 🔵 Low | N |
| ✅ Acceptable | N |

### Section 3 — Key Issues (ordered Critical → High → Medium)

List each issue as:
`[Section No.] [Issue Title] — [1–2 sentence description of the problem and its impact on the client]`

Include: all Critical issues + top 3 High issues. If Critical+High total is fewer than 5, include Medium issues to reach 5.

### Section 4 — Negotiation Priority
- **Must-haves** (Critical): Items that must be revised for the deal to be acceptable
- **Should-haves** (High): Items to negotiate; not individual dealbreakers but significant
- **Nice-to-haves** (Medium): Items worth raising if leverage and negotiating capital permit

### Section 5 — Review Notes
- Library mode: "House position comparison active" or "General review mode — no library match"
- Any review limitations (bilingual discrepancies, exhibits not analyzed, large-document chunking applied, etc.)
- Review date

### JSON Field Mapping for compile-report.js

When populating the `executive_summary` object in the review data JSON at Step 10, map the five template sections to the existing schema fields as follows:

| Template Section | JSON Field | Format |
|---|---|---|
| Section 1 — Contract Overview | Opening lines of `recommendation` | 2–3 sentences of prose |
| Section 2 — Overall Risk Assessment | `overall_risk` (string) + `risk_distribution` (object) | `"high"` / `{"critical":1,"high":3,...}` |
| Section 3 — Key Issues | `key_issues` (array) | Each item: `"[§No.] [Title] — [description]"` |
| Section 4 — Negotiation Priority | Middle paragraph of `recommendation` | Must-haves / Should-haves / Nice-to-haves prose |
| Section 5 — Review Notes | Final lines of `recommendation` | One line per note |

The `recommendation` field therefore carries Sections 1, 4, and 5 in sequence. The script renders it as a continuous narrative block; the three sections are separated by blank lines within the field.

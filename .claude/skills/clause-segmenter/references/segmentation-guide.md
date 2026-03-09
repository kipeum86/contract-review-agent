# Clause Segmentation Guide

## General Principles

1. **One clause = one logical provision**: A clause record represents a single, self-contained contractual provision. It may span one or more paragraphs but should cover a single topic.

2. **Follow the document's own structure**: Use the heading hierarchy and numbering as the primary guide for segmentation boundaries.

3. **Don't over-segment**: A section with three sub-provisions that all relate to the same topic (e.g., "Payment Terms") should be one clause, not three.

4. **Don't under-segment**: A long section titled "General Terms" that covers confidentiality, IP, and termination should be split into separate clauses.

## Segmentation Rules

### Where to Split

- At each numbered section or article boundary (e.g., "Section 1", "Article II")
- At each substantive subsection that covers a distinct topic
- At the boundary between recitals and operative provisions
- Between signature blocks and substantive content

### Where NOT to Split

- Within a single definition entry (even if it has sub-parts)
- Within a single representation/warranty item
- Between a clause heading and its body text
- Between a clause and its immediate proviso ("provided that...")
- Within enumerated sub-items that serve a single provision

### Special Cases

**Definitions Section:**
- The entire definitions section is one clause with `clause_type: definitions`
- Do NOT create separate clauses for each defined term

**Boilerplate Block:**
- Each boilerplate provision (severability, waiver, entire agreement, etc.) is a separate clause
- Even if they're in a single "Miscellaneous" or "General" section

**Tables:**
- A table is treated as part of the clause it belongs to
- If a table is a standalone schedule/exhibit, it's a separate clause

**Exhibits/Schedules:**
- Each exhibit or schedule is a separate clause with `clause_type: exhibits_schedules`
- Unless it has substantive provisions, in which case segment those provisions

## Clause Type Assignment

### Priority Order for Classification

1. **Exact match**: The clause heading or content directly maps to a taxonomy entry
2. **Functional match**: The clause serves the function described by a taxonomy entry, even if the heading differs
3. **Unmapped**: Cannot be confidently classified → use `clause_type: unmapped`

### Common Mapping Challenges

| Content Pattern | Correct clause_type |
|----------------|-------------------|
| "This Agreement shall be governed by the laws of..." | `governing_law` |
| "Either party may terminate this Agreement upon 30 days written notice..." | `termination_for_convenience` |
| "Neither party shall be liable for indirect, incidental..." | `exclusion_of_damages` |
| "The total aggregate liability shall not exceed..." | `liability_cap` |
| "The Receiving Party shall maintain the confidentiality..." | `confidentiality` |
| "All intellectual property created under..." | `ip_ownership` |
| "This Agreement constitutes the entire agreement..." | `entire_agreement` |
| "Any dispute arising out of this Agreement shall be..." | varies: `arbitration`, `jurisdiction`, or `dispute_escalation` |

### When to Use `unmapped`

- The clause doesn't fit any taxonomy entry
- You're uncertain between two categories and can't confidently choose
- The clause is highly specialized and domain-specific

**Never guess.** An `unmapped` clause triggers no quality penalty below the 30% threshold. A wrongly classified clause can lead to incorrect analysis.

## Output Format

```json
{
  "clause_id": "clause-001",
  "section_no": "1.1",
  "heading": "Definitions",
  "clause_type": "definitions",
  "text": "Full text of the clause...",
  "defined_terms_used": ["Agreement", "Party", "Effective Date"],
  "cross_refs": ["Section 5.2", "Exhibit A"],
  "paragraph_count": 15
}
```

## Quality Self-Check

After segmentation, verify:
- [ ] Every substantive section from the outline is represented
- [ ] No sections were accidentally skipped
- [ ] Clause text is exact (not paraphrased)
- [ ] clause_type assignments are confident
- [ ] Unmapped ratio is < 30%
- [ ] Total clause count is ≥ 5

---

## Korean Contract Patterns

### Article / Section Numbering Hierarchy

Korean contracts follow a three-level hierarchy. Apply the segmentation rules in the table:

| Korean Level | Notation | English Equivalent | Segmentation Rule |
|---|---|---|---|
| 조 (Article) | 제X조 | Article / Section | Always split at each 제X조 — never merge two articles into one clause |
| 항 (Paragraph) | ①②③ or 제X항 | Subsection | Split only if covering a clearly distinct substantive topic |
| 호 (Item) | 1. 2. 3. | Enumerated item | Keep together unless each item independently constitutes a distinct obligation |

**Key rule**: A new 제X조 always starts a new clause record. Sub-clauses (항/호) remain within the same clause unless they cover clearly separate topics (e.g., 제5조 that contains both confidentiality and IP ownership → split into two clauses with the same `section_no`).

### Bilingual Contracts (국영문 병기)

When Korean and English text appear for the same provision:
- Treat as **one clause** — include both language versions in the `text` field, Korean first
- Set `language` to the primary operative language; add `"bilingual": true` as an extra field in the clause JSON
- If the two versions appear to conflict in scope or meaning, add `"bilingual_discrepancy_risk": true` as a top-level field in the clause JSON (not inside `cross_refs`)
- Do **not** create two separate clause records for the same provision in two languages

### Common Korean Clause Type Mappings

| Korean Content Pattern | Correct `clause_type` |
|---|---|
| "이 계약에서 사용하는 용어의 정의는 다음과 같다" | `definitions` |
| "이 계약은 [날짜]부터 효력을 발생한다" | `duration` |
| "어느 일방은 ... 일의 서면 통지로 이 계약을 해지할 수 있다" | `termination_for_convenience` |
| "당사자 일방이 이 계약을 위반한 경우 ..." | `termination_for_cause` |
| "이 계약에 의해 창출된 지식재산권은 ..." | `ip_ownership` |
| "수령인은 비밀정보를 제3자에게 공개하여서는 아니 된다" | `confidentiality` |
| "일방 당사자의 총 책임은 ... 을 초과하지 아니한다" | `liability_cap` |
| "이 계약은 대한민국 법률에 의해 규율된다" | `governing_law` |
| "이 계약으로부터 발생하는 분쟁은 [법원/중재]에서 해결한다" | `arbitration` or `jurisdiction` |
| "을은 갑에게 ... 원을 지급한다" (단순 대가 조항) | `fees` |

### KVCA Standard Form Notes

KVCA(한국벤처캐피탈협회) standard investment agreements follow a predictable article pattern. When identified:
- 제1조 (목적) → `recitals`
- 제2조 (정의) → `definitions`
- 주식 인수·발행 관련 조항 → `purchase_price` or `conditions_precedent`
- 진술 및 보장 조항 → `representations_and_warranties`
- 손해배상 조항 → `indemnification`

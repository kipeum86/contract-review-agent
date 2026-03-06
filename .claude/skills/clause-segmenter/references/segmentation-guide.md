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

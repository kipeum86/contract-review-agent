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

For each clause:

1. **Read** the target clause text completely
2. **Compare** against the matched library clause (house position)
3. **Check** the playbook for this clause type (if available):
   - Is the clause within the preferred tier?
   - Does it match an acceptable alternative?
   - Has it fallen to fallback territory?
   - Does it hit a prohibited position?
4. **Assess** the risk in context:
   - What is the commercial impact?
   - What is the legal exposure?
   - Is this a standard market position?
   - What does the matter context suggest (leverage, priority areas)?
5. **Grade** the risk level
6. **Document** the reasoning (minimum 2 sentences)

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

The matter context affects risk grading:
- **High leverage**: Be stricter. Even Medium deviations may warrant redline.
- **Low leverage**: Be pragmatic. Focus on Critical and High only.
- **Priority areas**: Flag these even at lower risk levels.
- **Party role**: Understand our position (buyer/seller/licensor/licensee).

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

# Audience Firewall Rules

## Core Principle

`[EXTERNAL]` comments are visible to the counterparty.
`[INTERNAL]` comments are for internal use only.

**Never allow internal strategy information to appear in external-facing content.**

## What MUST NOT appear in `[EXTERNAL]` comments

1. **Negotiation strategy**: "We should push back on this because..."
2. **Fallback positions**: "If they reject, we can accept..."
3. **Leverage information**: "We have leverage here because..."
4. **Internal priorities**: "This is our top priority / not important to us"
5. **Budget or authority limits**: "Our maximum is..." / "We are authorized to..."
6. **Risk tolerance**: "We are willing to accept this risk"
7. **Internal disagreements**: "Legal wants X but business prefers Y"
8. **References to internal-only materials**: citing documents marked `external_safe: false`
9. **Assessment of counterparty's position**: "They probably won't accept..."
10. **Time pressure**: "We need to close by..." / "We're under deadline"

## What SHOULD appear in `[EXTERNAL]` comments

1. **Objective legal concerns**: "This clause lacks a limitation period"
2. **Market standard references**: "Market standard includes a mutual cap"
3. **Ambiguity identification**: "The scope of 'Confidential Information' is ambiguous"
4. **Proposed alternatives**: "We suggest the following alternative language..."
5. **Regulatory concerns**: "This may conflict with GDPR requirements"
6. **Practical concerns**: "The notice period may be insufficient for..."

## Validation Process

### Per-Comment Validation

Before finalizing each individual `[EXTERNAL]` comment:

1. **Read the comment in full**
2. **Ask**: "If the counterparty reads this, would it reveal our strategy?"
3. **Check**: Does it reference any material marked `external_safe: false`?
4. **Check**: Does it contain any of the prohibited patterns above?
5. **If any check fails**: Delete and regenerate

### Batch Validation (mandatory — after ALL comments are generated)

After all `[EXTERNAL]` comments for the contract are written, re-read every comment as a complete set:

1. **Check for distributed information leakage** — information that reveals internal strategy only when multiple comments are read in combination. Examples:
   - Comment A says "market standard allows X months"; Comment B says "this term aligns with our expectations" — together they expose our acceptable range
   - Multiple comments each narrowing or expanding a definition in ways that collectively reveal our interpretation of scope
   - A series of comments that, read in sequence, makes our negotiation priority order obvious

2. **If distributed leakage is found**: Revise or remove the comments that contribute to the pattern; ensure each comment is defensible in isolation and as part of the full set

3. **Log any `[MANUAL_REQUIRED]` outcomes** to `working/comments/firewall-log.json` with `clause_id` and reason

## Failure Protocol

- First violation → delete and regenerate
- Second violation → delete and regenerate with explicit firewall reminder
- Third violation → clear comment entirely and set to:
  `"[MANUAL_REQUIRED] Audience firewall could not be satisfied. Manual drafting required."`

## Source Material Rules

- Only materials with `external_safe: true` may be referenced in external comments
- Playbook content is **always internal-only** unless explicitly marked external_safe
- Comment bank entries in `comment-bank/external/` are pre-approved for external use
- Comment bank entries in `comment-bank/internal/` are **never** for external use

## External-Clean DOCX

The `strip-internal-comments.py` script removes all `[INTERNAL]` comments.
This is a **safety-critical** automated step. Both DOCX versions (internal + external-clean) are always generated together. The user should always review the external-clean version before sending to counterparty.

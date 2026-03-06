# Contract Re-review — Delta Analysis

You are re-reviewing a revised contract draft against a prior review round. The counterparty has returned a marked-up or revised version, and you need to analyze what changed.

$ARGUMENTS

---

## Prerequisites

- A revised contract file must be in the `input/` folder
- An existing matter with a prior round must exist in `contract-review/matters/`
- If the matter ID is not provided, list available matters and ask the user to select one

## Process

### Step 1: Round registration

Create `round_{N+1}/` folder under the existing matter. Link to the prior round in `round-meta.json`.

### Step 2: Parse the revised contract

Apply the same parsing pipeline as `/contract-review` (normalize, classify, structural parse, clause segmentation). Store outputs in `round_{N+1}/working/`.

### Step 3: Clause-level diff

Compare each clause in the current version against the prior round:
- **unchanged** — identical text
- **modified** — text changed (identify: narrowing, broadening, clarification, etc.)
- **added** — new clause not in prior round
- **removed** — clause from prior round no longer present

### Step 4: Full re-analysis

Re-analyze ALL clauses (not just changed ones) with the prior round's analysis as context. For each clause, include:
- `delta_summary` — what changed compared to prior assessment
- `prior_risk_level` — risk level from the previous round
- Current risk assessment

### Step 5: Delta report

Generate a delta report (DOCX) in `output/` with four sections:
1. **Negotiation Progress** — which prior redline requests were accepted, partially accepted, or rejected
2. **New Issues** — clauses that worsened or newly appeared
3. **Resolved Issues** — clauses that improved or were accepted
4. **Remaining Open Items** — unresolved issues carried forward

### Step 6: DOCX redline & comments

Apply tracked changes and comments to the revised DOCX, same as `/contract-review`. Generate both internal and external-clean versions.

### Step 7: Human review

Present a summary of the delta analysis and file paths to all deliverables.

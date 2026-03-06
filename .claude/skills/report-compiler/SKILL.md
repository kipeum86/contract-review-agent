# report-compiler Skill

Compile analysis results into professional DOCX report deliverables.

## Capabilities

1. **Analysis Report** (`scripts/compile-report.js`)
   - Generates DOCX with Executive Summary + per-clause analysis
   - Input: review data JSON with clauses, executive_summary, risk distribution
   - Usage: `node compile-report.js <review_data.json> <output.docx>`

2. **Delta Report** (`scripts/compile-delta-report.js`)
   - Generates DOCX for re-review delta reports
   - Sections: Negotiation Progress, New Issues, Resolved Issues, Open Items
   - Usage: `node compile-delta-report.js <delta_data.json> <output.docx>`

## When to Use

- WF2 Step 10: compile analysis report
- WF4 Step 5: compile delta report
- WF5 Step 7: generate draft contract DOCX (uses docx library directly)

## Input JSON Format — Analysis Report

```json
{
  "contract_info": { "title": "...", "contract_family": "nda" },
  "review_mode": "moderate",
  "general_review_mode": false,
  "executive_summary": {
    "overall_risk": "high",
    "key_issues": ["Issue 1", "Issue 2"],
    "recommendation": "...",
    "risk_distribution": { "critical": 1, "high": 3, "medium": 5 }
  },
  "clauses": [
    {
      "clause_id": "clause-001",
      "section_no": "1.1",
      "heading": "Definitions",
      "clause_type": "definitions",
      "risk_level": "low",
      "risk_rationale": "...",
      "divergence": "...",
      "playbook_tier": "preferred",
      "playbook_missing": false,
      "suggested_redline": "...",
      "internal_note": "..."
    }
  ]
}
```

## Input JSON Format — Delta Report

```json
{
  "current_round": 2,
  "prior_round": 1,
  "negotiation_progress": {
    "accepted": ["Item 1"],
    "partially_accepted": ["Item 2"],
    "rejected": ["Item 3"]
  },
  "clauses": [
    {
      "clause_id": "...",
      "diff_status": "modified",
      "risk_level": "high",
      "prior_risk_level": "critical",
      "risk_direction": "improved",
      "delta_summary": "..."
    }
  ]
}
```

## Language Policy

- Redline text: always in the contract's original language
- Analysis report: follows user's prompt language or explicit language instruction
- The report compiler accepts the text as-is; language adaptation happens at analysis time

# report-compiler Skill

Compile analysis results into professional DOCX report deliverables.

## Capabilities

1. **Analysis Report** (`scripts/compile-report.js`)
   - Generates DOCX with either:
     - legacy flat Executive Summary + per-clause analysis, or
     - numbered Section 1-6 English structure when `executive_summary.negotiation_priority` is present, or
     - Korean memorandum-style opinion when report language is Korean
   - Korean renderer applies A4 sizing, CJK font, minimal color, disclaimer blocks, information block, and signature block
   - Input: review data JSON with clauses, executive_summary, risk distribution, optional memorandum metadata, and optional matter working directory for baseline trace injection
   - Usage: `node compile-report.js <review_data.json> <output.docx> [<matter_working_dir>]`

2. **Delta Report** (`scripts/compile-delta-report.js`)
   - Generates DOCX for re-review delta reports
   - Sections: Negotiation Progress, New Issues, Resolved Issues, Open Items
   - Usage: `node compile-delta-report.js <delta_data.json> <output.docx>`

## When to Use

- WF2 Step 10: compile analysis report
- WF4 Step 5: compile delta report

## WF5 Status

- This skill currently ships only the review-report compilers above.
- The repository does **not** yet include a dedicated Workflow 5 draft-contract DOCX packager or end-to-end drafting orchestrator.
- For drafting, treat DOCX packaging as manual/experimental until a separate WF5 compiler is added.

## Input JSON Format — Analysis Report

```json
{
  "report_language": "ko",
  "contract_info": { "title": "...", "contract_family": "nda" },
  "review_mode": "moderate",
  "general_review_mode": false,
  "memo_metadata": {
    "date": "2026-03-27",
    "recipient": "Client Name",
    "reference": "GC",
    "sender": "Law Firm Name",
    "subject": "법률 검토 의견서",
    "signer": "담당 변호사"
  },
  "background_facts": ["..."],
  "questions_presented": ["..."],
  "limitations_disclaimer": "...",
  "closing_disclaimer": "...",
  "executive_summary": {
    "overview": "2-3 sentence contract overview",
    "overall_risk": "high",
    "key_issues": ["Issue 1", "Issue 2"],
    "negotiation_priority": {
      "must_haves": ["Item 1"],
      "should_haves": ["Item 2"],
      "nice_to_haves": ["Item 3"]
    },
    "review_notes": [
      "Library mode: House position comparison active",
      "Review date: 2026-04-10"
    ],
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
      "suggested_action": "Tighten the liability cap to direct damages only.",
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
- English reports render as numbered Section 1-6 output when `executive_summary.negotiation_priority` is present; otherwise the compiler falls back to the legacy flat structure for backward compatibility
- Korean reports render as memorandum-style DOCX when `report_language`, `language`, or the supplied text indicates Korean
- The report compiler accepts the substantive text as-is; language adaptation and memorandum metadata selection happen at render time

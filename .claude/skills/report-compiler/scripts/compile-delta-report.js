#!/usr/bin/env node
/**
 * Compile delta report for re-reviews (Workflow 4).
 * Generates a DOCX report focused on changes between negotiation rounds:
 *   1. Negotiation Progress Summary
 *   2. New Issues
 *   3. Resolved Issues
 *   4. Remaining Open Items
 *
 * Usage: node compile-delta-report.js <delta_data.json> <output.docx>
 */

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  AlignmentType, ShadingType, PageBreak
} = require('docx');

const RISK_COLORS = {
  critical: 'CC0000',
  high: 'FF6600',
  medium: 'FFAA00',
  low: '339966',
  acceptable: '009900',
};

function riskBadge(level) {
  const color = RISK_COLORS[level] || '666666';
  return new TextRun({
    text: ` [${(level || 'N/A').toUpperCase()}] `,
    bold: true,
    color,
    size: 20,
  });
}

function diffStatusLabel(status) {
  const labels = {
    unchanged: { text: 'Unchanged', color: '999999' },
    modified: { text: 'Modified', color: '0066CC' },
    added: { text: 'Added', color: '009900' },
    removed: { text: 'Removed', color: 'CC0000' },
  };
  const cfg = labels[status] || { text: status, color: '666666' };
  return new TextRun({ text: `[${cfg.text}]`, bold: true, color: cfg.color });
}

function createNegotiationProgress(data) {
  const sections = [];
  const progress = data.negotiation_progress || {};

  sections.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: 'Negotiation Progress Summary', bold: true })],
    })
  );

  // Round info
  sections.push(
    new Paragraph({
      children: [
        new TextRun({ text: `Round ${data.current_round || '?'}`, bold: true }),
        new TextRun({ text: ` (compared to Round ${data.prior_round || '?'})` }),
      ],
    })
  );

  // Accepted
  const accepted = progress.accepted || [];
  if (accepted.length > 0) {
    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
        children: [new TextRun({ text: 'Our Requests — Accepted', color: '009900' })],
      })
    );
    for (const item of accepted) {
      sections.push(
        new Paragraph({
          bullet: { level: 0 },
          children: [new TextRun({ text: item })],
        })
      );
    }
  }

  // Partially accepted
  const partial = progress.partially_accepted || [];
  if (partial.length > 0) {
    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
        children: [new TextRun({ text: 'Our Requests — Partially Accepted', color: 'FFAA00' })],
      })
    );
    for (const item of partial) {
      sections.push(
        new Paragraph({
          bullet: { level: 0 },
          children: [new TextRun({ text: item })],
        })
      );
    }
  }

  // Rejected
  const rejected = progress.rejected || [];
  if (rejected.length > 0) {
    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
        children: [new TextRun({ text: 'Our Requests — Rejected', color: 'CC0000' })],
      })
    );
    for (const item of rejected) {
      sections.push(
        new Paragraph({
          bullet: { level: 0 },
          children: [new TextRun({ text: item })],
        })
      );
    }
  }

  return sections;
}

function createNewIssues(clauses) {
  const sections = [];
  const newIssues = clauses.filter(c =>
    c.diff_status === 'added' ||
    (c.diff_status === 'modified' && c.risk_direction === 'worsened')
  );

  sections.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
      children: [new TextRun({ text: 'New Issues', bold: true })],
    })
  );

  if (newIssues.length === 0) {
    sections.push(
      new Paragraph({
        children: [new TextRun({ text: 'No new issues identified.', italics: true })],
      })
    );
  } else {
    for (const clause of newIssues) {
      sections.push(...renderDeltaClause(clause));
    }
  }

  return sections;
}

function createResolvedIssues(clauses) {
  const sections = [];
  const resolved = clauses.filter(c =>
    c.diff_status === 'removed' ||
    (c.diff_status === 'modified' && c.risk_direction === 'improved')
  );

  sections.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
      children: [new TextRun({ text: 'Resolved Issues', bold: true })],
    })
  );

  if (resolved.length === 0) {
    sections.push(
      new Paragraph({
        children: [new TextRun({ text: 'No issues resolved in this round.', italics: true })],
      })
    );
  } else {
    for (const clause of resolved) {
      sections.push(...renderDeltaClause(clause));
    }
  }

  return sections;
}

function createOpenItems(clauses) {
  const sections = [];
  const open = clauses.filter(c =>
    c.risk_level && !['acceptable', 'low'].includes(c.risk_level) &&
    c.diff_status !== 'removed'
  );

  sections.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
      children: [new TextRun({ text: 'Remaining Open Items', bold: true })],
    })
  );

  if (open.length === 0) {
    sections.push(
      new Paragraph({
        children: [new TextRun({ text: 'No remaining open items.', italics: true })],
      })
    );
  } else {
    for (const clause of open) {
      sections.push(...renderDeltaClause(clause));
    }
  }

  return sections;
}

function renderDeltaClause(clause) {
  const parts = [];
  const heading = clause.heading || clause.clause_type || 'Unnamed';
  const sectionNo = clause.section_no ? `${clause.section_no} ` : '';

  parts.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_3,
      spacing: { before: 200 },
      children: [
        new TextRun({ text: `${sectionNo}${heading}  ` }),
        diffStatusLabel(clause.diff_status),
        new TextRun({ text: '  ' }),
        riskBadge(clause.risk_level),
      ],
    })
  );

  // Risk change
  if (clause.prior_risk_level && clause.risk_level !== clause.prior_risk_level) {
    parts.push(
      new Paragraph({
        children: [
          new TextRun({ text: 'Risk Change: ', bold: true }),
          riskBadge(clause.prior_risk_level),
          new TextRun({ text: ' → ' }),
          riskBadge(clause.risk_level),
        ],
      })
    );
  }

  // Delta summary
  if (clause.delta_summary) {
    parts.push(
      new Paragraph({
        spacing: { before: 100 },
        children: [new TextRun({ text: clause.delta_summary })],
      })
    );
  }

  return parts;
}

async function compileDeltaReport(inputPath, outputPath) {
  const rawData = fs.readFileSync(inputPath, 'utf-8');
  const data = JSON.parse(rawData);

  const clauses = data.clauses || [];

  const children = [
    ...createNegotiationProgress(data),
    new Paragraph({ children: [new PageBreak()] }),
    ...createNewIssues(clauses),
    ...createResolvedIssues(clauses),
    ...createOpenItems(clauses),
  ];

  const doc = new Document({
    creator: 'Contract Review Agent',
    description: 'Contract Review Delta Report',
    sections: [{
      properties: {
        page: {
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  fs.writeFileSync(outputPath, buffer);

  return {
    success: true,
    output_path: outputPath,
    clauses_count: clauses.length,
    file_size: buffer.length,
  };
}

async function main() {
  if (process.argv.length < 4) {
    console.log(JSON.stringify({
      error: 'Usage: compile-delta-report.js <delta_data.json> <output.docx>'
    }));
    process.exit(1);
  }

  try {
    const result = await compileDeltaReport(process.argv[2], process.argv[3]);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, success: false }));
    process.exit(1);
  }
}

main();

#!/usr/bin/env node
/**
 * Compile analysis results into a DOCX report.
 * Generates: Executive Summary (1 page) + Full per-clause analysis.
 *
 * Usage: node compile-report.js <review_data.json> <output.docx>
 */

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  AlignmentType, BorderStyle, Table, TableRow, TableCell,
  WidthType, ShadingType, PageBreak
} = require('docx');

// Risk level colors
const RISK_COLORS = {
  critical: 'CC0000',
  high: 'FF6600',
  medium: 'FFAA00',
  low: '339966',
  acceptable: '009900',
};

const RISK_LABELS = {
  critical: 'CRITICAL',
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
  acceptable: 'ACCEPTABLE',
};

function createRiskBadge(riskLevel) {
  const color = RISK_COLORS[riskLevel] || '666666';
  const label = RISK_LABELS[riskLevel] || riskLevel.toUpperCase();
  return new TextRun({
    text: ` [${label}] `,
    bold: true,
    color: color,
    size: 20,
  });
}

function createExecutiveSummary(data) {
  const sections = [];
  const summary = data.executive_summary || {};

  sections.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: 'Executive Summary', bold: true })],
    })
  );

  // Overall risk profile
  const overallRisk = summary.overall_risk || 'Not assessed';
  sections.push(
    new Paragraph({
      spacing: { before: 200, after: 100 },
      children: [
        new TextRun({ text: 'Overall Risk Profile: ', bold: true, size: 24 }),
        createRiskBadge(overallRisk.toLowerCase()),
      ],
    })
  );

  // Review mode
  if (data.review_mode) {
    sections.push(
      new Paragraph({
        children: [
          new TextRun({ text: 'Review Mode: ', bold: true }),
          new TextRun({ text: data.review_mode }),
        ],
      })
    );
  }

  // Contract info
  if (data.contract_info) {
    const info = data.contract_info;
    sections.push(
      new Paragraph({
        spacing: { before: 200 },
        children: [
          new TextRun({ text: 'Contract: ', bold: true }),
          new TextRun({ text: info.title || 'Untitled' }),
        ],
      })
    );
    if (info.contract_family) {
      sections.push(
        new Paragraph({
          children: [
            new TextRun({ text: 'Type: ', bold: true }),
            new TextRun({ text: info.contract_family }),
          ],
        })
      );
    }
  }

  // Key issues
  const keyIssues = summary.key_issues || [];
  if (keyIssues.length > 0) {
    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
        children: [new TextRun({ text: 'Key Issues', bold: true })],
      })
    );
    for (const issue of keyIssues) {
      sections.push(
        new Paragraph({
          bullet: { level: 0 },
          children: [new TextRun({ text: issue })],
        })
      );
    }
  }

  // Recommendation
  if (summary.recommendation) {
    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
        children: [new TextRun({ text: 'Recommendation', bold: true })],
      })
    );
    sections.push(
      new Paragraph({
        children: [new TextRun({ text: summary.recommendation })],
      })
    );
  }

  // Risk distribution
  const stats = summary.risk_distribution || {};
  if (Object.keys(stats).length > 0) {
    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
        children: [new TextRun({ text: 'Risk Distribution', bold: true })],
      })
    );
    for (const [level, count] of Object.entries(stats)) {
      sections.push(
        new Paragraph({
          children: [
            createRiskBadge(level),
            new TextRun({ text: `: ${count} clause(s)` }),
          ],
        })
      );
    }
  }

  // Page break after executive summary
  sections.push(new Paragraph({ children: [new PageBreak()] }));

  return sections;
}

function createClauseAnalysis(clauses) {
  const sections = [];

  sections.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: 'Per-Clause Analysis', bold: true })],
    })
  );

  for (const clause of clauses) {
    // Clause heading
    const heading = clause.heading || clause.clause_type || 'Unnamed Clause';
    const sectionNo = clause.section_no ? `${clause.section_no} ` : '';

    sections.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 400 },
        children: [
          new TextRun({ text: `${sectionNo}${heading}` }),
          new TextRun({ text: '  ' }),
          createRiskBadge(clause.risk_level || 'acceptable'),
        ],
      })
    );

    // Clause type
    if (clause.clause_type) {
      sections.push(
        new Paragraph({
          children: [
            new TextRun({ text: 'Clause Type: ', bold: true, size: 20, color: '666666' }),
            new TextRun({ text: clause.clause_type, size: 20, color: '666666' }),
          ],
        })
      );
    }

    // Risk assessment
    if (clause.risk_rationale) {
      sections.push(
        new Paragraph({
          spacing: { before: 100 },
          children: [
            new TextRun({ text: 'Risk Assessment: ', bold: true }),
          ],
        })
      );
      sections.push(
        new Paragraph({
          children: [new TextRun({ text: clause.risk_rationale })],
        })
      );
    }

    // Divergence from house position
    if (clause.divergence) {
      sections.push(
        new Paragraph({
          spacing: { before: 100 },
          children: [
            new TextRun({ text: 'Divergence: ', bold: true }),
          ],
        })
      );
      sections.push(
        new Paragraph({
          children: [new TextRun({ text: clause.divergence })],
        })
      );
    }

    // Playbook tier
    if (clause.playbook_tier) {
      sections.push(
        new Paragraph({
          children: [
            new TextRun({ text: 'Playbook Tier: ', bold: true }),
            new TextRun({ text: clause.playbook_tier }),
            clause.playbook_missing ? new TextRun({ text: ' (playbook missing)', italics: true, color: 'FF6600' }) : new TextRun({ text: '' }),
          ],
        })
      );
    }

    // Suggested redline
    if (clause.suggested_redline) {
      sections.push(
        new Paragraph({
          spacing: { before: 100 },
          children: [
            new TextRun({ text: 'Suggested Redline:', bold: true }),
          ],
        })
      );
      sections.push(
        new Paragraph({
          indent: { left: 400 },
          shading: { type: ShadingType.CLEAR, fill: 'F5F5F5' },
          children: [new TextRun({ text: clause.suggested_redline, italics: true })],
        })
      );
    }

    // Internal note
    if (clause.internal_note) {
      sections.push(
        new Paragraph({
          spacing: { before: 100 },
          children: [
            new TextRun({ text: '[INTERNAL] ', bold: true, color: '0066CC' }),
            new TextRun({ text: clause.internal_note }),
          ],
        })
      );
    }
  }

  return sections;
}

async function compileReport(inputPath, outputPath) {
  const rawData = fs.readFileSync(inputPath, 'utf-8');
  const data = JSON.parse(rawData);

  const clauses = data.clauses || data.analysis || [];

  const children = [
    ...createExecutiveSummary(data),
    ...createClauseAnalysis(clauses),
  ];

  // General review mode notice
  if (data.general_review_mode) {
    children.unshift(
      new Paragraph({
        spacing: { before: 200, after: 200 },
        shading: { type: ShadingType.CLEAR, fill: 'FFF3CD' },
        children: [
          new TextRun({
            text: 'NOTICE: This report was produced in General Review Mode without library-backed house position comparison.',
            bold: true,
            color: '856404',
          }),
        ],
      })
    );
  }

  const doc = new Document({
    creator: 'Contract Review Agent',
    description: 'Contract Review Analysis Report',
    sections: [{
      properties: {
        page: {
          margin: {
            top: 1440,    // 1 inch
            right: 1440,
            bottom: 1440,
            left: 1440,
          },
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
      error: 'Usage: compile-report.js <review_data.json> <output.docx>'
    }));
    process.exit(1);
  }

  try {
    const result = await compileReport(process.argv[2], process.argv[3]);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, success: false }));
    process.exit(1);
  }
}

main();

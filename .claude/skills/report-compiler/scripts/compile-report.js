#!/usr/bin/env node
/**
 * Compile analysis results into a DOCX report.
 *
 * - Generic renderer: Executive Summary + per-clause analysis
 * - Korean renderer: Memorandum-style opinion aligned to the local style guide
 *
 * Usage: node compile-report.js <review_data.json> <output.docx> [<matter_working_dir>]
 */

const fs = require('fs');
const path = require('path');
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  BorderStyle,
  Table,
  TableRow,
  TableCell,
  WidthType,
  ShadingType,
  PageBreak,
  convertMillimetersToTwip,
  PageOrientation,
} = require('docx');

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

const KOREAN_RISK_LABELS = {
  critical: '매우 높음',
  high: '높음',
  medium: '보통',
  low: '낮음',
  acceptable: '수용 가능',
};

const LATIN_FONT = 'Times New Roman';
const CJK_FONT = 'Malgun Gothic';
const DEFAULT_FONT = {
  ascii: LATIN_FONT,
  hAnsi: LATIN_FONT,
  eastAsia: CJK_FONT,
};
const DEFAULT_TEXT_COLOR = '000000';
const DEFAULT_FONT_SIZE = 22; // 11pt in half-points
const DEFAULT_PARAGRAPH_SPACING = {
  line: 276, // 1.15
  after: 120, // 6pt
};
const A4_PAGE_SIZE = {
  width: convertMillimetersToTwip(210),
  height: convertMillimetersToTwip(297),
  orientation: PageOrientation.PORTRAIT,
};
const PAGE_MARGINS = {
  top: 1440,
  right: 1440,
  bottom: 1440,
  left: 1440,
};


function containsHangul(value) {
  return /[\u3131-\uD79D]/.test(value || '');
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return '';
}

function normalizeList(value) {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => normalizeList(item));
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : [];
  }
  if (typeof value === 'object') {
    return Object.values(value).flatMap((item) => normalizeList(item));
  }
  return [];
}

// ─────────────────────────────────────────────────────────────────────────────
// Domain Reference Forced-Load — baseline trace injection (v2.1, P4)
//
// Reads the per-matter baseline-context/loaded.json (written by
// .claude/scripts/load-domain-references.sh) and appends a forensic trace
// line before rendering. For the numbered English renderer, the trace is
// appended to `executive_summary.review_notes`; for legacy English and Korean
// paths it is appended to `executive_summary.recommendation`.
//
// CRITICAL — backward compatibility:
//   If matterWorkingDir is null/undefined (v1 invocation: `compile-report.js
//   review.json out.docx` with only 2 args), this function is a no-op.
//   The output DOCX is identical to the v1 behavior — no warnings, no
//   appended text. This preserves re-compilation of pre-v2.1 review data.
//
// Hallucination resistance:
//   The trace line content is read from the JSON file directly. The LLM
//   never writes this line. sha256 + canary heading in the JSON cannot be
//   guessed without actually running the loader against the real files.
//
// See: docs/ko/domain-reference-forced-load.md (Section 9.3)
// ─────────────────────────────────────────────────────────────────────────────
function injectBaselineTrace(data, matterWorkingDir) {
  // Backward compat: if caller did not provide matter dir, do nothing.
  if (!matterWorkingDir) {
    return;
  }

  const tracePath = path.join(matterWorkingDir, 'baseline-context', 'loaded.json');

  // Ensure executive_summary exists
  data.executive_summary = data.executive_summary || {};
  const summary = data.executive_summary;

  const appendTraceText = (text) => {
    const useReviewNotes = resolveReportLanguage(data) === 'en' && !!summary.negotiation_priority;
    if (useReviewNotes) {
      summary.review_notes = normalizeList(summary.review_notes);
      summary.review_notes.push(text);
      return;
    }

    const existing = summary.recommendation || '';
    summary.recommendation = existing
      ? `${existing}\n\n${text}`
      : text;
  };

  if (!fs.existsSync(tracePath)) {
    appendTraceText(
      '⚠️ REVIEW INVALID — baseline-context/loaded.json missing. ' +
      'Analysis may have relied on pretrained knowledge only. ' +
      'Re-run review recommended.',
    );
    return;
  }

  let trace;
  try {
    trace = JSON.parse(fs.readFileSync(tracePath, 'utf8'));
  } catch (err) {
    appendTraceText(
      `⚠️ REVIEW INVALID — baseline-context/loaded.json malformed: ${err.message}`,
    );
    return;
  }

  if (!trace || !Array.isArray(trace.files_loaded) || trace.files_loaded.length === 0) {
    appendTraceText(
      '⚠️ REVIEW INVALID — loaded.json has no files_loaded entries.',
    );
    return;
  }

  const fileSummaries = trace.files_loaded.map((f) => {
    const canary = f.last_section_heading || 'n/a';
    return `${f.name} (${f.byte_size} bytes, sha256: ${f.sha256_short}, canary: "${canary}")`;
  }).join(', ');

  let traceLine = `Baselines applied: ${fileSummaries}. ` +
                  `Loaded at ${trace.loaded_at} via ${trace.source}.`;

  // Add chunking info if present (chunk-*.json siblings of loaded.json)
  try {
    const baselineDir = path.join(matterWorkingDir, 'baseline-context');
    const chunkFiles = fs.readdirSync(baselineDir)
      .filter((f) => /^chunk-\d+\.json$/.test(f));
    if (chunkFiles.length > 0) {
      traceLine += ` Chunking: ${chunkFiles.length} chunks with per-chunk re-injection.`;
    }
  } catch (_) {
    // chunk enumeration is optional; ignore errors
  }

  appendTraceText(traceLine);
}

function resolveReportLanguage(data) {
  const explicitLanguage = firstNonEmpty(
    data.report_language,
    data.language,
    data.contract_info?.language,
    data.memo_metadata?.language,
  ).toLowerCase();

  if (explicitLanguage.startsWith('ko')) {
    return 'ko';
  }
  if (explicitLanguage.startsWith('en')) {
    return 'en';
  }

  const samples = [
    data.contract_info?.title,
    data.executive_summary?.recommendation,
    ...(data.executive_summary?.key_issues || []),
  ].filter(Boolean);

  return samples.some(containsHangul) ? 'ko' : 'en';
}

function styledRun(text, options = {}) {
  return new TextRun({
    text,
    bold: options.bold ?? false,
    color: options.color ?? DEFAULT_TEXT_COLOR,
    size: options.size ?? DEFAULT_FONT_SIZE,
    font: options.font ?? DEFAULT_FONT,
    break: options.break,
  });
}

function createParagraph(children, options = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [children],
    alignment: options.alignment,
    heading: options.heading,
    indent: options.indent,
    shading: options.shading,
    border: options.border,
    spacing: {
      ...DEFAULT_PARAGRAPH_SPACING,
      ...(options.spacing || {}),
    },
  });
}

function createRiskBadge(riskLevel) {
  const color = RISK_COLORS[riskLevel] || '666666';
  const label = RISK_LABELS[riskLevel] || (riskLevel || 'UNKNOWN').toUpperCase();
  return new TextRun({
    text: ` [${label}] `,
    bold: true,
    color,
    size: 20,
  });
}

function createExecutiveSummary(data) {
  const sections = [];
  const summary = data.executive_summary || {};

  sections.push(
    createParagraph([styledRun('Executive Summary', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
    }),
  );

  const overallRisk = summary.overall_risk || 'Not assessed';
  sections.push(
    createParagraph(
      [
        styledRun('Overall Risk Profile: ', { bold: true, size: 24 }),
        createRiskBadge(overallRisk.toLowerCase()),
      ],
      { spacing: { before: 200, after: 100 } },
    ),
  );

  if (data.review_mode) {
    sections.push(
      createParagraph([
        styledRun('Review Mode: ', { bold: true }),
        styledRun(data.review_mode),
      ]),
    );
  }

  if (data.contract_info) {
    const info = data.contract_info;
    sections.push(
      createParagraph(
        [styledRun('Contract: ', { bold: true }), styledRun(info.title || 'Untitled')],
        { spacing: { before: 200 } },
      ),
    );

    if (info.contract_family) {
      sections.push(
        createParagraph([
          styledRun('Type: ', { bold: true }),
          styledRun(info.contract_family),
        ]),
      );
    }
  }

  const keyIssues = summary.key_issues || [];
  if (keyIssues.length > 0) {
    sections.push(
      createParagraph([styledRun('Key Issues', { bold: true })], {
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
      }),
    );
    for (const issue of keyIssues) {
      sections.push(new Paragraph({
        bullet: { level: 0 },
        spacing: DEFAULT_PARAGRAPH_SPACING,
        children: [styledRun(issue)],
      }));
    }
  }

  if (summary.recommendation) {
    sections.push(
      createParagraph([styledRun('Recommendation', { bold: true })], {
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
      }),
    );
    sections.push(createParagraph([styledRun(summary.recommendation)]));
  }

  const stats = summary.risk_distribution || {};
  if (Object.keys(stats).length > 0) {
    sections.push(
      createParagraph([styledRun('Risk Distribution', { bold: true })], {
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300 },
      }),
    );
    for (const [level, count] of Object.entries(stats)) {
      sections.push(
        createParagraph([createRiskBadge(level), styledRun(`: ${count} clause(s)`)]),
      );
    }
  }

  sections.push(new Paragraph({ children: [new PageBreak()] }));
  return sections;
}

function createNumberedExecutiveSummary(data) {
  const sections = [];
  const summary = data.executive_summary || {};
  const contractInfo = data.contract_info || {};

  sections.push(
    createParagraph([styledRun('Section 1. Executive Summary', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
    }),
  );

  if (summary.overview) {
    sections.push(createParagraph([styledRun(summary.overview)], {
      spacing: { before: 200, after: 100 },
    }));
  }

  const overallRisk = summary.overall_risk || 'Not assessed';
  sections.push(
    createParagraph(
      [
        styledRun('Overall Risk Profile: ', { bold: true, size: 24 }),
        createRiskBadge(overallRisk.toLowerCase()),
      ],
      { spacing: { before: 200, after: 100 } },
    ),
  );

  if (data.review_mode) {
    sections.push(
      createParagraph([
        styledRun('Review Mode: ', { bold: true }),
        styledRun(data.review_mode),
      ]),
    );
  }

  if (contractInfo.title) {
    sections.push(
      createParagraph(
        [styledRun('Contract: ', { bold: true }), styledRun(contractInfo.title)],
        { spacing: { before: 200 } },
      ),
    );
  }
  if (contractInfo.contract_family) {
    sections.push(
      createParagraph([
        styledRun('Type: ', { bold: true }),
        styledRun(contractInfo.contract_family),
      ]),
    );
  }
  if (contractInfo.language) {
    sections.push(
      createParagraph([
        styledRun('Contract Language: ', { bold: true }),
        styledRun(contractInfo.language),
      ]),
    );
  }
  if (contractInfo.jurisdiction) {
    sections.push(
      createParagraph([
        styledRun('Jurisdiction: ', { bold: true }),
        styledRun(contractInfo.jurisdiction),
      ]),
    );
  }
  if (contractInfo.governing_law) {
    sections.push(
      createParagraph([
        styledRun('Governing Law: ', { bold: true }),
        styledRun(contractInfo.governing_law),
      ]),
    );
  }

  sections.push(
    createParagraph([styledRun('Section 2. Overall Risk Assessment', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
    }),
  );

  const stats = summary.risk_distribution || {};
  if (Object.keys(stats).length > 0) {
    sections.push(
      createParagraph([styledRun('Risk Distribution', { bold: true })], {
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200 },
      }),
    );
    for (const [level, count] of Object.entries(stats)) {
      sections.push(
        createParagraph([createRiskBadge(level), styledRun(`: ${count} clause(s)`)]),
      );
    }
  } else {
    sections.push(createParagraph([styledRun('Risk distribution not available.', { color: '666666' })]));
  }

  sections.push(
    createParagraph([styledRun('Section 3. Key Issues', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
    }),
  );

  const keyIssues = normalizeList(summary.key_issues);
  if (keyIssues.length === 0) {
    sections.push(createParagraph([styledRun('No key issues flagged.', { color: '666666' })]));
  } else {
    for (const issue of keyIssues) {
      sections.push(new Paragraph({
        bullet: { level: 0 },
        spacing: DEFAULT_PARAGRAPH_SPACING,
        children: [styledRun(issue)],
      }));
    }
  }

  sections.push(
    createParagraph([styledRun('Section 4. Negotiation Priority', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
    }),
  );

  const priority = summary.negotiation_priority || {};
  const priorityGroups = [
    { key: 'must_haves', label: '4.1 Must-haves (Critical)' },
    { key: 'should_haves', label: '4.2 Should-haves (High)' },
    { key: 'nice_to_haves', label: '4.3 Nice-to-haves (Medium)' },
  ];
  for (const group of priorityGroups) {
    sections.push(
      createParagraph([styledRun(group.label, { bold: true })], {
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200 },
      }),
    );
    const items = normalizeList(priority[group.key]);
    if (items.length === 0) {
      sections.push(createParagraph([styledRun('— (none)', { color: '666666' })]));
      continue;
    }
    for (const item of items) {
      sections.push(new Paragraph({
        bullet: { level: 0 },
        spacing: DEFAULT_PARAGRAPH_SPACING,
        children: [styledRun(item)],
      }));
    }
  }

  sections.push(
    createParagraph([styledRun('Section 5. Review Notes', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400 },
    }),
  );

  const notes = normalizeList(summary.review_notes);
  if (notes.length === 0 && !summary.recommendation) {
    sections.push(createParagraph([styledRun('No additional review notes.', { color: '666666' })]));
  } else {
    for (const note of notes) {
      sections.push(new Paragraph({
        bullet: { level: 0 },
        spacing: DEFAULT_PARAGRAPH_SPACING,
        children: [styledRun(note)],
      }));
    }
    if (summary.recommendation) {
      sections.push(
        createParagraph([styledRun('Recommendation', { bold: true })], {
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200 },
        }),
      );
      sections.push(createParagraph([styledRun(summary.recommendation)]));
    }
  }

  return sections;
}

function createClauseAnalysis(clauses) {
  const sections = [];

  sections.push(
    createParagraph([styledRun('Per-Clause Analysis', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
    }),
  );

  for (const clause of clauses) {
    const heading = clause.heading || clause.clause_type || 'Unnamed Clause';
    const sectionNo = clause.section_no ? `${clause.section_no} ` : '';

    sections.push(
      createParagraph(
        [
          styledRun(`${sectionNo}${heading}`),
          styledRun('  '),
          createRiskBadge(clause.risk_level || 'acceptable'),
        ],
        {
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 400 },
        },
      ),
    );

    if (clause.clause_type) {
      sections.push(
        createParagraph([
          styledRun('Clause Type: ', { bold: true, size: 20, color: '666666' }),
          styledRun(clause.clause_type, { size: 20, color: '666666' }),
        ]),
      );
    }

    if (clause.risk_rationale) {
      sections.push(createParagraph([styledRun('Risk Assessment: ', { bold: true })], { spacing: { before: 100 } }));
      sections.push(createParagraph([styledRun(clause.risk_rationale)]));
    }

    if (clause.divergence) {
      sections.push(createParagraph([styledRun('Divergence: ', { bold: true })], { spacing: { before: 100 } }));
      sections.push(createParagraph([styledRun(clause.divergence)]));
    }

    if (clause.playbook_tier) {
      const tierText = clause.playbook_missing
        ? `${clause.playbook_tier} (playbook missing)`
        : clause.playbook_tier;
      sections.push(
        createParagraph([
          styledRun('Playbook Tier: ', { bold: true }),
          styledRun(tierText),
        ]),
      );
    }

    if (clause.suggested_redline) {
      sections.push(createParagraph([styledRun('Suggested Redline:', { bold: true })], { spacing: { before: 100 } }));
      sections.push(
        createParagraph([styledRun(clause.suggested_redline)], {
          indent: { left: 400 },
          shading: { type: ShadingType.CLEAR, fill: 'F5F5F5' },
        }),
      );
    }

    if (clause.internal_note) {
      sections.push(
        createParagraph([
          styledRun('[INTERNAL] ', { bold: true, color: '0066CC' }),
          styledRun(clause.internal_note),
        ], { spacing: { before: 100 } }),
      );
    }
  }

  return sections;
}

function createNumberedClauseAnalysis(clauses) {
  const sections = [];

  sections.push(
    createParagraph([styledRun('Section 6. Clause-by-Clause Analysis', { bold: true })], {
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 500 },
    }),
  );

  if (!clauses.length) {
    sections.push(createParagraph([styledRun('No clauses analyzed.', { color: '666666' })]));
    return sections;
  }

  for (const clause of clauses) {
    const heading = clause.heading || clause.clause_type || 'Unnamed Clause';
    const sectionNo = clause.section_no ? `${clause.section_no} ` : '';

    sections.push(
      createParagraph(
        [
          styledRun(`${sectionNo}${heading}`),
          styledRun('  '),
          createRiskBadge(clause.risk_level || 'acceptable'),
        ],
        {
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 400 },
        },
      ),
    );

    if (clause.clause_type) {
      sections.push(
        createParagraph([
          styledRun('Clause Type: ', { bold: true, size: 20, color: '666666' }),
          styledRun(clause.clause_type, { size: 20, color: '666666' }),
        ]),
      );
    }

    if (clause.risk_rationale) {
      sections.push(createParagraph([styledRun('Risk Assessment: ', { bold: true })], { spacing: { before: 100 } }));
      sections.push(createParagraph([styledRun(clause.risk_rationale)]));
    }

    if (clause.divergence) {
      sections.push(createParagraph([styledRun('Divergence: ', { bold: true })], { spacing: { before: 100 } }));
      sections.push(createParagraph([styledRun(clause.divergence)]));
    }

    if (clause.playbook_tier) {
      const tierText = clause.playbook_missing
        ? `${clause.playbook_tier} (playbook missing)`
        : clause.playbook_tier;
      sections.push(
        createParagraph([
          styledRun('Playbook Tier: ', { bold: true }),
          styledRun(tierText),
        ]),
      );
    }

    if (clause.suggested_action) {
      sections.push(createParagraph([styledRun('Suggested Action: ', { bold: true })], { spacing: { before: 100 } }));
      sections.push(createParagraph([styledRun(clause.suggested_action)]));
    }
  }

  return sections;
}

function formatKoreanDate(rawValue) {
  if (!rawValue) {
    return formatKoreanDate(new Date());
  }
  if (rawValue instanceof Date) {
    return `${rawValue.getFullYear()}. ${rawValue.getMonth() + 1}. ${rawValue.getDate()}.`;
  }

  const parsed = new Date(rawValue);
  if (!Number.isNaN(parsed.getTime())) {
    return formatKoreanDate(parsed);
  }

  return String(rawValue);
}

function koreanLetter(index) {
  const letters = ['가', '나', '다', '라', '마', '바', '사', '아', '자', '차', '카', '타', '파', '하'];
  return letters[index] || `${index + 1}`;
}

function koreanRiskLabel(level) {
  return KOREAN_RISK_LABELS[(level || '').toLowerCase()] || '검토 필요';
}

function resolveMemoMetadata(data) {
  const meta = data.memo_metadata || {};
  const contractInfo = data.contract_info || {};

  return {
    date: formatKoreanDate(meta.date || data.report_date || contractInfo.date),
    recipient: firstNonEmpty(meta.recipient, contractInfo.client_name, contractInfo.recipient, '의뢰인 귀중'),
    reference: firstNonEmpty(meta.reference, contractInfo.reference),
    sender: firstNonEmpty(meta.sender, contractInfo.sender, '법무법인 [작성 주체 확인 필요]'),
    subject: firstNonEmpty(
      meta.subject,
      contractInfo.subject,
      contractInfo.title ? `${contractInfo.title} 관련 법률 검토 의견서` : '',
      '계약 검토 의견서',
    ),
    signer: firstNonEmpty(meta.signer, contractInfo.signer, '[담당자 확인 필요]'),
  };
}

function createInfoBlockTable(metadata) {
  const rows = [
    ['수 신', metadata.recipient],
    metadata.reference ? ['참 조', metadata.reference] : null,
    ['발 신', metadata.sender],
    ['제 목', metadata.subject],
  ].filter(Boolean);

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map(([label, value]) => new TableRow({
      children: [
        new TableCell({
          width: { size: 1800, type: WidthType.DXA },
          children: [
            createParagraph([styledRun(`${label} :`, { bold: true })], {
              spacing: { after: 60, before: 0, line: 240 },
            }),
          ],
        }),
        new TableCell({
          width: { size: 7200, type: WidthType.DXA },
          children: [
            createParagraph([styledRun(value)], {
              spacing: { after: 60, before: 0, line: 240 },
            }),
          ],
        }),
      ],
    })),
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      left: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      right: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: '000000' },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: '000000' },
    },
  });
}

function createMemoSectionTitle(text) {
  return createParagraph([styledRun(text, { bold: true })], {
    spacing: { before: 240, after: 120 },
  });
}

function createMemoBodyParagraph(text, options = {}) {
  return createParagraph([styledRun(text)], options);
}

function createMemoLabelValueParagraph(label, value) {
  return createParagraph([
    styledRun(`${label} `, { bold: true }),
    styledRun(value),
  ]);
}

function resolveBackgroundFacts(data) {
  const facts = normalizeList(
    data.background_facts
    || data.memo_metadata?.background_facts
    || data.contract_info?.background_facts,
  );

  if (facts.length > 0) {
    return facts;
  }

  const fallback = firstNonEmpty(
    data.contract_info?.title && `본 의견서는 ${data.contract_info.title}에 대한 검토를 전제로 작성되었습니다.`,
    data.general_review_mode && '본 검토는 라이브러리 비교 근거 없이 일반 계약 검토 모드로 수행되었습니다.',
  );

  return fallback ? [fallback] : ['검토의 전제가 되는 배경 사실은 제공된 계약서 및 입력 정보에 한정됩니다.'];
}

function resolveQuestionsPresented(data) {
  const questions = normalizeList(
    data.questions_presented
    || data.questions
    || data.memo_metadata?.questions_presented
    || data.executive_summary?.key_issues,
  );

  if (questions.length > 0) {
    return questions;
  }

  return ['본 계약의 주요 위험 요소와 수정 필요 사항'];
}

function resolveLimitationsDisclaimer(data) {
  return firstNonEmpty(
    data.limitations_disclaimer,
    data.memo_metadata?.limitations_disclaimer,
    '아래 의견은 귀사가 제공한 자료 및 정보만을 전제로 귀사가 문의한 사항에 국한된 법률검토임을 말씀드립니다. 제공된 자료 및 정보 이외에 다른 특별한 사정이 있는 경우 그 법률적 판단이 달라질 수 있습니다.',
  );
}

function resolveConclusionText(data) {
  const summary = data.executive_summary || {};
  return firstNonEmpty(
    summary.recommendation,
    data.conclusion,
    (() => {
      const level = (summary.overall_risk || '').toLowerCase();
      if (level === 'critical' || level === 'high') {
        return '검토 결과, 본 계약은 중요한 위험 조항이 포함되어 있어 주요 조항의 수정 및 협의가 필요할 것으로 사료됩니다.';
      }
      if (level === 'medium') {
        return '검토 결과, 본 계약은 일부 유의가 필요한 조항이 존재하므로 핵심 쟁점 위주로 수정 여부를 검토할 필요가 있습니다.';
      }
      return '검토 결과, 본 계약은 전반적으로 수용 가능한 범위에 있으나 구체적 사실관계에 따라 추가 확인이 필요할 수 있습니다.';
    })(),
  );
}

function resolveClosingDisclaimer(data) {
  return firstNonEmpty(
    data.closing_disclaimer,
    data.memo_metadata?.closing_disclaimer,
    '이상은 제공된 자료와 현 시점의 법령 및 통상적 해석을 기초로 한 의견이며, 추가 사실관계 또는 관련 법령의 변경이 있는 경우 결론이 달라질 수 있습니다.',
  );
}

function createMemoCallout(text) {
  return createParagraph([styledRun(text, { bold: true })], {
    border: {
      top: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      left: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      right: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
    },
    spacing: { before: 120, after: 120 },
  });
}

function createKoreanClauseAnalysis(clauses) {
  const sections = [];

  if (!clauses.length) {
    sections.push(createMemoBodyParagraph('검토 대상 조항 정보가 별도로 제공되지 않았습니다.'));
    return sections;
  }

  clauses.forEach((clause, index) => {
    const heading = clause.heading || clause.clause_type || `쟁점 ${index + 1}`;
    const sectionNo = clause.section_no ? `${clause.section_no} ` : '';

    sections.push(
      createParagraph(
        [styledRun(`${koreanLetter(index)}. ${sectionNo}${heading}`, { bold: true })],
        { spacing: { before: 240, after: 80 } },
      ),
    );

    sections.push(
      createMemoLabelValueParagraph('위험도:', koreanRiskLabel(clause.risk_level || 'acceptable')),
    );

    if (clause.clause_type) {
      sections.push(createMemoLabelValueParagraph('조항 유형:', clause.clause_type));
    }

    if (clause.risk_rationale) {
      sections.push(createMemoLabelValueParagraph('검토 의견:', clause.risk_rationale));
    }

    if (clause.divergence) {
      sections.push(createMemoLabelValueParagraph('기준 대비 차이:', clause.divergence));
    }

    if (clause.playbook_tier) {
      const tierText = clause.playbook_missing
        ? `${clause.playbook_tier} (playbook 부재)`
        : clause.playbook_tier;
      sections.push(createMemoLabelValueParagraph('검토 기준 등급:', tierText));
    }

    if (clause.suggested_redline) {
      sections.push(createParagraph([styledRun('권고 수정 문안', { bold: true })], { spacing: { before: 100, after: 60 } }));
      sections.push(
        createParagraph([styledRun(clause.suggested_redline)], {
          border: {
            top: { style: BorderStyle.SINGLE, size: 2, color: '000000' },
            bottom: { style: BorderStyle.SINGLE, size: 2, color: '000000' },
            left: { style: BorderStyle.SINGLE, size: 2, color: '000000' },
            right: { style: BorderStyle.SINGLE, size: 2, color: '000000' },
          },
          spacing: { before: 60, after: 120 },
        }),
      );
    }

    if (clause.internal_note) {
      sections.push(createMemoLabelValueParagraph('내부 검토 메모:', clause.internal_note));
    }
  });

  return sections;
}

function createKoreanMemorandum(data) {
  const sections = [];
  const metadata = resolveMemoMetadata(data);
  const backgroundFacts = resolveBackgroundFacts(data);
  const questions = resolveQuestionsPresented(data);
  const clauses = data.clauses || data.analysis || [];

  sections.push(
    createParagraph([styledRun('MEMORANDUM', { bold: true, size: 28 })], {
      alignment: AlignmentType.CENTER,
      spacing: { after: 120 },
    }),
  );
  sections.push(
    createParagraph([styledRun(metadata.date)], {
      alignment: AlignmentType.CENTER,
      spacing: { after: 180 },
    }),
  );
  sections.push(createInfoBlockTable(metadata));

  sections.push(createMemoSectionTitle('1. 질의의 배경'));
  backgroundFacts.forEach((fact) => {
    sections.push(
      new Paragraph({
        spacing: DEFAULT_PARAGRAPH_SPACING,
        bullet: { level: 0 },
        children: [styledRun(fact)],
      }),
    );
  });

  sections.push(createMemoSectionTitle('2. 질의 사항'));
  questions.forEach((question, index) => {
    sections.push(createMemoBodyParagraph(`${index + 1}. ${question}`));
  });

  sections.push(createMemoSectionTitle('3. 법률 의견의 한계'));
  sections.push(createMemoBodyParagraph(resolveLimitationsDisclaimer(data)));

  if (data.general_review_mode) {
    sections.push(
      createMemoCallout('본 의견서는 library-backed house position 비교 없이 일반 계약 검토 기준에 따라 작성되었습니다.'),
    );
  }

  sections.push(createMemoSectionTitle('4. 검토의견'));
  sections.push(...createKoreanClauseAnalysis(clauses));

  sections.push(createMemoSectionTitle('5. 결론'));
  sections.push(createMemoBodyParagraph(resolveConclusionText(data)));

  sections.push(createParagraph([styledRun(resolveClosingDisclaimer(data))], {
    spacing: { before: 240, after: 180 },
  }));

  sections.push(createParagraph([styledRun(metadata.sender, { bold: true })], {
    alignment: AlignmentType.RIGHT,
    spacing: { after: 60 },
  }));
  sections.push(createParagraph([styledRun(metadata.signer)], {
    alignment: AlignmentType.RIGHT,
  }));

  return sections;
}

function buildChildren(data) {
  const clauses = data.clauses || data.analysis || [];
  if (resolveReportLanguage(data) === 'ko') {
    return createKoreanMemorandum(data);
  }

  const useNumberedStructure = !!(
    data.executive_summary
    && data.executive_summary.negotiation_priority
  );

  const children = useNumberedStructure
    ? [
      ...createNumberedExecutiveSummary(data),
      ...createNumberedClauseAnalysis(clauses),
    ]
    : [
      ...createExecutiveSummary(data),
      ...createClauseAnalysis(clauses),
    ];

  if (data.general_review_mode) {
    children.unshift(
      createParagraph(
        [styledRun('NOTICE: This report was produced in General Review Mode without library-backed house position comparison.', {
          bold: true,
          color: '856404',
        })],
        {
          spacing: { before: 200, after: 200 },
          shading: { type: ShadingType.CLEAR, fill: 'FFF3CD' },
        },
      ),
    );
  }

  return children;
}

async function compileReport(inputPath, outputPath, matterWorkingDir) {
  const rawData = fs.readFileSync(inputPath, 'utf-8');
  const data = JSON.parse(rawData);

  // v2.1 — inject baseline trace line BEFORE rendering so both English and
  // Korean renderers see the mutated summary.recommendation. No-op when
  // matterWorkingDir is omitted (backward compat with v1 2-arg invocation).
  injectBaselineTrace(data, matterWorkingDir);

  const children = buildChildren(data);

  const doc = new Document({
    creator: 'Contract Review Agent',
    description: resolveReportLanguage(data) === 'ko'
      ? 'Korean Memorandum-Style Contract Review Report'
      : 'Contract Review Analysis Report',
    sections: [{
      properties: {
        page: {
          margin: PAGE_MARGINS,
          size: A4_PAGE_SIZE,
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

  const clauses = data.clauses || data.analysis || [];
  return {
    success: true,
    output_path: outputPath,
    clauses_count: clauses.length,
    file_size: buffer.length,
    report_language: resolveReportLanguage(data),
  };
}

async function main() {
  if (process.argv.length < 4) {
    console.log(JSON.stringify({
      error: 'Usage: compile-report.js <review_data.json> <output.docx> [<matter_working_dir>]',
    }));
    process.exit(1);
  }

  try {
    // Optional 3rd arg: matter working directory (for baseline trace injection).
    // Omitting it preserves v1 behavior exactly (no injection, no warnings).
    const matterWorkingDir = process.argv[4] || null;
    const result = await compileReport(process.argv[2], process.argv[3], matterWorkingDir);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.log(JSON.stringify({ error: err.message, success: false }));
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  compileReport,
  buildChildren,
  resolveReportLanguage,
  injectBaselineTrace,
  createNumberedExecutiveSummary,
  createNumberedClauseAnalysis,
};

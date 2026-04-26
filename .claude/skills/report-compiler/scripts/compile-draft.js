#!/usr/bin/env node
/**
 * Compile a contract draft (draft.json) into a DOCX document.
 *
 * Usage: node compile-draft.js <draft.json> <output.docx>
 *
 * Input: JSON with:
 *   - draft_metadata: { title, parties, contract_type, language, matter_id, date_created }
 *   - sections[]: { section_number, title, text, subsections[]? }
 *   - contract_text?: { preamble, signature_blocks[] }
 *   - self_review?: { issues[] }
 *   - defined_terms?: string[]
 *   - output_options?: { include_self_review_notes: boolean }
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
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  convertMillimetersToTwip,
  PageOrientation,
} = require('docx');

// ── Typography & Layout ──────────────────────────────────────────

const LATIN_FONT = 'Times New Roman';
const CJK_FONT = 'Malgun Gothic';
const DEFAULT_FONT = { ascii: LATIN_FONT, hAnsi: LATIN_FONT, eastAsia: CJK_FONT };
const DEFAULT_TEXT_COLOR = '000000';
const DEFAULT_FONT_SIZE = 22; // 11pt
const HEADING_1_SIZE = 28;    // 14pt
const HEADING_2_SIZE = 24;    // 12pt
const DEFAULT_PARAGRAPH_SPACING = { line: 276, after: 120 };
const A4_PAGE_SIZE = {
  width: convertMillimetersToTwip(210),
  height: convertMillimetersToTwip(297),
  orientation: PageOrientation.PORTRAIT,
};
const PAGE_MARGINS = { top: 1440, right: 1440, bottom: 1440, left: 1440 };

// ── Helpers ──────────────────────────────────────────────────────

function containsHangul(value) {
  return /[\u3131-\uD79D]/.test(value || '');
}

function resolveLanguage(data) {
  const meta = data.draft_metadata || {};
  const lang = (meta.language || '').toLowerCase();
  if (lang.startsWith('ko')) return 'ko';
  if (lang.startsWith('en')) return 'en';
  const samples = [meta.title, ...(data.sections || []).map((s) => s.title)].filter(Boolean);
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
    italics: options.italics ?? false,
    underline: options.underline,
  });
}

function createParagraph(children, options = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [children],
    alignment: options.alignment,
    heading: options.heading,
    indent: options.indent,
    spacing: { ...DEFAULT_PARAGRAPH_SPACING, ...(options.spacing || {}) },
  });
}

function validateDraftData(data) {
  const errors = [];
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return ['draft data must be a JSON object'];
  }

  const meta = data.draft_metadata;
  if (!meta || typeof meta !== 'object' || Array.isArray(meta)) {
    errors.push('draft_metadata is required');
  } else {
    ['title', 'contract_type', 'language', 'matter_id'].forEach((field) => {
      if (!meta[field] || typeof meta[field] !== 'string') {
        errors.push(`draft_metadata.${field} is required`);
      }
    });
  }

  if (!Array.isArray(data.sections) || data.sections.length === 0) {
    errors.push('sections must be a non-empty array');
  } else {
    data.sections.forEach((section, index) => {
      if (!section || typeof section !== 'object' || Array.isArray(section)) {
        errors.push(`sections[${index}] must be an object`);
        return;
      }
      if (!section.title || typeof section.title !== 'string') {
        errors.push(`sections[${index}].title is required`);
      }
      const hasText = typeof section.text === 'string' && section.text.trim();
      const hasSubsections = Array.isArray(section.subsections) && section.subsections.length > 0;
      if (!hasText && !hasSubsections) {
        errors.push(`sections[${index}] must include text or subsections`);
      }
    });
  }

  return errors;
}

// ── Defined Term Bolding ─────────────────────────────────────────

function buildDefinedTermSet(data) {
  const terms = new Set();
  if (Array.isArray(data.defined_terms)) {
    data.defined_terms.forEach((t) => terms.add(t));
  }
  return terms;
}

function splitByTerms(text, termsSet) {
  if (!termsSet.size) return [{ text, bold: false }];

  const sortedTerms = [...termsSet].sort((a, b) => b.length - a.length);
  const escaped = sortedTerms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${escaped.join('|')})`, 'g');

  const parts = [];
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index), bold: false });
    }
    parts.push({ text: match[0], bold: true });
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), bold: false });
  }
  return parts.length ? parts : [{ text, bold: false }];
}

function textToRuns(text, termsSet) {
  const parts = splitByTerms(text, termsSet);
  return parts.map((p) => styledRun(p.text, { bold: p.bold }));
}

// ── Section Numbering ────────────────────────────────────────────

function formatSectionNumber(num, lang) {
  if (lang === 'ko') return `제${num}조`;
  return `Article ${num}`;
}

function formatSubsectionNumber(parentNum, childNum, lang) {
  if (lang === 'ko') return `${parentNum}.${childNum}`;
  return `${parentNum}.${childNum}`;
}

// ── Document Sections ────────────────────────────────────────────

function buildTitle(data) {
  const meta = data.draft_metadata || {};
  const title = meta.title || 'Contract Draft';
  return [
    createParagraph([styledRun(title, { bold: true, size: 32 })], {
      alignment: AlignmentType.CENTER,
      spacing: { before: 400, after: 200 },
    }),
  ];
}

function buildPreamble(data, termsSet) {
  const preamble = data.contract_text?.preamble;
  if (!preamble) return [];
  return [
    createParagraph(textToRuns(preamble, termsSet), { spacing: { after: 200 } }),
  ];
}

function buildSections(data, termsSet, lang) {
  const sections = data.sections || [];
  const children = [];

  for (const section of sections) {
    const num = section.section_number || '';
    const heading = num
      ? `${formatSectionNumber(num, lang)}  ${section.title || ''}`
      : section.title || '';

    children.push(
      createParagraph([styledRun(heading, { bold: true, size: HEADING_1_SIZE })], {
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 300, after: 100 },
      }),
    );

    if (section.text) {
      const paragraphs = section.text.split(/\n{2,}/);
      for (const para of paragraphs) {
        if (para.trim()) {
          children.push(createParagraph(textToRuns(para.trim(), termsSet)));
        }
      }
    }

    if (Array.isArray(section.subsections)) {
      for (const sub of section.subsections) {
        const subNum = sub.number || '';
        const subHeading = subNum
          ? `${formatSubsectionNumber(num, subNum, lang)}  ${sub.title || ''}`
          : sub.title || '';

        children.push(
          createParagraph([styledRun(subHeading, { bold: true, size: HEADING_2_SIZE })], {
            heading: HeadingLevel.HEADING_2,
            spacing: { before: 200, after: 80 },
          }),
        );

        if (sub.text) {
          const paragraphs = sub.text.split(/\n{2,}/);
          for (const para of paragraphs) {
            if (para.trim()) {
              children.push(
                createParagraph(textToRuns(para.trim(), termsSet), {
                  indent: { left: 360 },
                }),
              );
            }
          }
        }
      }
    }
  }

  return children;
}

function buildSignatureBlocks(data, lang) {
  const blocks = data.contract_text?.signature_blocks;
  if (!Array.isArray(blocks) || !blocks.length) return [];

  const children = [
    createParagraph([], { spacing: { before: 600 } }),
  ];

  for (const block of blocks) {
    const partyName = block.party || '';
    const date = block.date || '[Date]';
    const signatureLine = block.signature_line || '____________________';

    children.push(createParagraph([], { spacing: { before: 300 } }));
    children.push(createParagraph([styledRun(signatureLine)], { spacing: { after: 40 } }));
    children.push(
      createParagraph([styledRun(lang === 'ko' ? '성명: ' : 'Name: '), styledRun(partyName, { bold: true })]),
    );
    children.push(
      createParagraph([styledRun(lang === 'ko' ? '날짜: ' : 'Date: '), styledRun(date)]),
    );
  }

  return children;
}

function buildSelfReviewNotes(data, lang) {
  if (data.output_options?.include_self_review_notes !== true) return [];

  const issues = data.self_review?.issues;
  if (!Array.isArray(issues) || !issues.length) return [];

  const heading = lang === 'ko' ? '[INTERNAL] 자체 검토 소견' : '[INTERNAL] Self-Review Notes';
  const children = [
    createParagraph([styledRun(heading, { bold: true, color: '856404' })], {
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 400, after: 100 },
    }),
  ];

  for (const issue of issues) {
    const severity = (issue.severity || 'info').toUpperCase();
    const section = issue.section || '';
    const prefix = section ? `[${severity}] ${lang === 'ko' ? '제' : ''}${section}${lang === 'ko' ? '조' : ''}: ` : `[${severity}] `;
    children.push(
      createParagraph([
        styledRun(prefix, { bold: true, color: '856404' }),
        styledRun(issue.description || ''),
      ]),
    );
    if (issue.suggested_fix) {
      children.push(
        createParagraph([
          styledRun(lang === 'ko' ? '  \u2192 권고: ' : '  \u2192 Suggestion: ', { italics: true }),
          styledRun(issue.suggested_fix, { italics: true }),
        ], { indent: { left: 360 } }),
      );
    }
  }

  return children;
}

// ── Main ─────────────────────────────────────────────────────────

async function compileDraft(inputPath, outputPath) {
  const rawData = fs.readFileSync(inputPath, 'utf-8');
  const data = JSON.parse(rawData);
  const validationErrors = validateDraftData(data);
  if (validationErrors.length) {
    throw new Error(`Invalid draft.json: ${validationErrors.join('; ')}`);
  }
  const lang = resolveLanguage(data);
  const termsSet = buildDefinedTermSet(data);

  const children = [
    ...buildTitle(data),
    ...buildPreamble(data, termsSet),
    ...buildSections(data, termsSet, lang),
    ...buildSignatureBlocks(data, lang),
    ...buildSelfReviewNotes(data, lang),
  ];

  const doc = new Document({
    creator: 'Contract Drafting Agent',
    description: `Contract Draft - ${data.draft_metadata?.title || 'Untitled'}`,
    sections: [{
      properties: {
        page: { margin: PAGE_MARGINS, size: A4_PAGE_SIZE },
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

  const meta = data.draft_metadata || {};
  return {
    success: true,
    output_path: outputPath,
    language: lang,
    title: meta.title || 'Untitled',
    sections_count: (data.sections || []).length,
    defined_terms_count: termsSet.size,
    self_review_issues: (data.self_review?.issues || []).length,
    self_review_notes_included: data.output_options?.include_self_review_notes === true,
    has_signature_blocks: !!(data.contract_text?.signature_blocks?.length),
  };
}

(async () => {
  if (process.argv.includes('--help') || process.argv.includes('-h')) {
    console.log(JSON.stringify({
      usage: 'compile-draft.js <draft.json> <output.docx>',
      required_fields: [
        'draft_metadata.title',
        'draft_metadata.contract_type',
        'draft_metadata.language',
        'draft_metadata.matter_id',
        'sections[]',
      ],
      optional_fields: [
        'defined_terms[]',
        'contract_text.preamble',
        'contract_text.signature_blocks[]',
        'self_review.issues[]',
        'output_options.include_self_review_notes',
      ],
    }, null, 2));
    process.exit(0);
  }

  if (process.argv.length < 4) {
    console.error(JSON.stringify({
      error: 'Usage: compile-draft.js <draft.json> <output.docx>',
    }));
    process.exit(1);
  }

  try {
    const result = await compileDraft(process.argv[2], process.argv[3]);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.error(JSON.stringify({
      error: err.message,
      stack: err.stack,
    }));
    process.exit(1);
  }
})();

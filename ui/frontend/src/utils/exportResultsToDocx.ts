/**
 * Client-side generator for a nicely-formatted Word (.docx) export of a
 * search result set, including the AI summary.
 *
 * The export is produced entirely in the browser using the `docx` package —
 * no backend round-trip is required. The resulting Blob can be handed to
 * `file-saver`'s `saveAs` for download.
 *
 * Design goals (see also the unit tests):
 *  - Cover page with query, dataset, timestamp, and result count.
 *  - AI summary with markdown-aware headings / bullets / emphasis.
 *  - One "card" per result: clickable title, metadata line, breadcrumb of
 *    headings, and the FULL excerpt (never truncated).
 *  - Every document title is a working hyperlink (pdf_url when available,
 *    otherwise the canonical evidencelab.ai deep-link).
 */
import {
  AlignmentType,
  Document,
  ExternalHyperlink,
  Footer,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageNumber,
  Paragraph,
  TextRun,
  convertInchesToTwip,
} from 'docx';
import type { SearchResult } from '../types/api';

export interface ExportOptions {
  query: string;
  aiSummary?: string;
  results: SearchResult[];
  dataSource?: string;
  /** Public origin of the deployed Evidence Lab — used to build fallback
   *  hyperlinks when a result has no pdf_url. Defaults to window.location.origin
   *  at runtime. Overridable for tests. */
  siteOrigin?: string;
  /** Injectable clock for deterministic tests. */
  now?: () => Date;
}

/** MIME type for a .docx file — exported so the call-site can set it on Blobs
 *  and tests can assert it. */
export const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Slugify a query into a safe filename fragment. */
const slugify = (s: string): string =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'search';

/** Build a filename like "evidencelab-search-<slug>-<YYYYMMDD-HHMM>.docx" */
export const buildExportFilename = (query: string, now: Date): string => {
  const pad = (n: number) => String(n).padStart(2, '0');
  const stamp =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `-${pad(now.getHours())}${pad(now.getMinutes())}`;
  return `evidencelab-search-${slugify(query)}-${stamp}.docx`;
};

/** Best-effort resolution of a clickable hyperlink for a result. */
export const resolveResultLink = (
  r: SearchResult,
  siteOrigin: string,
  dataSource?: string,
): string => {
  const directPdf =
    r.pdf_url ||
    r.metadata?.pdf_url ||
    r.metadata?.map_pdf_url ||
    r.metadata?.src_doc_raw_metadata?.pdf_url;
  if (typeof directPdf === 'string' && directPdf.trim()) {
    return directPdf.trim();
  }
  const report = r.report_url;
  if (typeof report === 'string' && report.trim()) return report.trim();

  const ds = dataSource || r.data_source || '';
  const page = typeof r.page_num === 'number' ? `#page=${r.page_num}` : '';
  const origin = siteOrigin.replace(/\/+$/, '');
  const query = ds ? `?data_source=${encodeURIComponent(ds)}` : '';
  return `${origin}/document/${r.doc_id}${query}${page}`;
};

/** Trim a block of text by (a) collapsing 3+ consecutive newlines into 2 and
 *  (b) trimming trailing whitespace on each line. Never truncates. */
const normaliseExcerpt = (s: string): string =>
  s
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/g, ''))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

/** Render inline markdown emphasis (`**bold**` and `*italic*`) into a list of
 *  TextRun children. Keeps the implementation tiny — we do not need a full
 *  markdown parser, just enough to survive what the AI summary endpoint emits.
 */
const inlineRuns = (text: string, base: { size?: number } = {}): TextRun[] => {
  const runs: TextRun[] = [];
  // Match **bold** | *italic* | `code`
  const re = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/g;
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) {
      runs.push(new TextRun({ text: text.slice(lastIndex, m.index), size: base.size }));
    }
    if (m[2] !== undefined) {
      runs.push(new TextRun({ text: m[2], bold: true, size: base.size }));
    } else if (m[3] !== undefined) {
      runs.push(new TextRun({ text: m[3], italics: true, size: base.size }));
    } else if (m[4] !== undefined) {
      runs.push(new TextRun({ text: m[4], font: 'Menlo', size: base.size }));
    }
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < text.length) {
    runs.push(new TextRun({ text: text.slice(lastIndex), size: base.size }));
  }
  return runs.length ? runs : [new TextRun({ text, size: base.size })];
};

const HEADING_LEVELS_BY_DEPTH: Record<number, (typeof HeadingLevel)[keyof typeof HeadingLevel]> = {
  1: HeadingLevel.HEADING_1,
  2: HeadingLevel.HEADING_2,
  3: HeadingLevel.HEADING_3,
  4: HeadingLevel.HEADING_4,
  5: HeadingLevel.HEADING_5,
  6: HeadingLevel.HEADING_6,
};

/** Try to match a single markdown line to a "block" Paragraph (heading,
 *  bullet, or ordered list item). Returns null when the line is part of a
 *  plain paragraph buffer. Extracted from {@link markdownToParagraphs} to
 *  keep per-line complexity flat. */
const matchBlockParagraph = (line: string): Paragraph | null => {
  const h = /^(#{1,6})\s+(.*)$/.exec(line);
  if (h) {
    const depth = h[1].length;
    const heading = HEADING_LEVELS_BY_DEPTH[depth] ?? HeadingLevel.HEADING_4;
    return new Paragraph({
      heading,
      children: inlineRuns(h[2]),
      spacing: { before: 200, after: 120 },
    });
  }
  const ul = /^[-*]\s+(.*)$/.exec(line);
  if (ul) {
    return new Paragraph({
      children: inlineRuns(ul[1]),
      bullet: { level: 0 },
      spacing: { after: 80 },
    });
  }
  const ol = /^(\d+)\.\s+(.*)$/.exec(line);
  if (ol) {
    return new Paragraph({
      children: inlineRuns(ol[2]),
      numbering: { reference: 'summary-ordered', level: 0 },
      spacing: { after: 80 },
    });
  }
  return null;
};

/** Convert a markdown-ish AI summary into docx Paragraphs. Supports:
 *   - ATX headings `##`, `###`, `####`
 *   - Unordered list items `- ` or `* `
 *   - Ordered list items `1. `
 *   - Blank-line paragraph breaks
 *   - Inline **bold**, *italic*, `code`
 *  Anything more exotic is rendered as plain paragraph text — acceptable for
 *  a dev-mode export and safe against unexpected AI output. */
export const markdownToParagraphs = (md: string): Paragraph[] => {
  const paragraphs: Paragraph[] = [];
  const lines = md.replace(/\r\n/g, '\n').split('\n');

  let buffer: string[] = [];
  const flushParagraph = () => {
    const text = buffer.join(' ').trim();
    buffer = [];
    if (text) {
      paragraphs.push(new Paragraph({ children: inlineRuns(text), spacing: { after: 120 } }));
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line === '') {
      flushParagraph();
      continue;
    }
    const block = matchBlockParagraph(line);
    if (block) {
      flushParagraph();
      paragraphs.push(block);
      continue;
    }
    buffer.push(line);
  }
  flushParagraph();
  return paragraphs;
};

// ---------------------------------------------------------------------------
// Builders — one per section of the docx
// ---------------------------------------------------------------------------

const buildCoverParagraphs = (
  opts: ExportOptions,
  now: Date,
): Paragraph[] => {
  const children: Paragraph[] = [];
  children.push(
    new Paragraph({
      heading: HeadingLevel.TITLE,
      alignment: AlignmentType.LEFT,
      children: [new TextRun({ text: 'Evidence Lab — Search Export', bold: true })],
    }),
  );
  children.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: opts.query || '(no query)', italics: true })],
      spacing: { after: 240 },
    }),
  );
  const meta: string[] = [];
  if (opts.dataSource) meta.push(`Dataset: ${opts.dataSource}`);
  meta.push(`Results: ${opts.results.length}`);
  meta.push(`Generated: ${now.toISOString().replace('T', ' ').slice(0, 16)} UTC`);
  children.push(
    new Paragraph({
      children: [new TextRun({ text: meta.join('  ·  '), size: 20, color: '555555' })],
      spacing: { after: 360 },
    }),
  );
  return children;
};

const buildSummarySection = (summary: string): Paragraph[] => {
  if (!summary.trim()) return [];
  const out: Paragraph[] = [];
  out.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: 'AI Summary' })],
      spacing: { before: 240, after: 120 },
    }),
  );
  out.push(...markdownToParagraphs(summary));
  return out;
};

const buildResultCard = (
  r: SearchResult,
  idx: number,
  siteOrigin: string,
  dataSource?: string,
): Paragraph[] => {
  const out: Paragraph[] = [];
  const altTitle = typeof r.document_title === 'string' ? r.document_title : '';
  const title =
    (r.title && r.title.trim()) ||
    (altTitle && altTitle.trim()) ||
    '(untitled document)';
  const href = resolveResultLink(r, siteOrigin, dataSource);

  out.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_3,
      spacing: { before: 240, after: 80 },
      children: [
        new TextRun({ text: `${idx + 1}. `, bold: true }),
        new ExternalHyperlink({
          link: href,
          children: [new TextRun({ text: title, bold: true, style: 'Hyperlink' })],
        }),
      ],
    }),
  );

  const metaParts: string[] = [];
  if (r.organization) metaParts.push(String(r.organization));
  if (r.year) metaParts.push(String(r.year));
  if (typeof r.page_num === 'number') metaParts.push(`p. ${r.page_num}`);
  if (r.data_source || dataSource) metaParts.push(String(r.data_source || dataSource));
  if (typeof r.score === 'number') metaParts.push(`score ${r.score.toFixed(3)}`);
  out.push(
    new Paragraph({
      spacing: { after: 60 },
      children: [new TextRun({ text: metaParts.join('  ·  '), italics: true, size: 18, color: '555555' })],
    }),
  );

  const headings = Array.isArray(r.headings) ? r.headings.filter(Boolean) : [];
  if (headings.length) {
    out.push(
      new Paragraph({
        spacing: { after: 80 },
        children: [
          new TextRun({ text: 'Section: ', bold: true, size: 18 }),
          new TextRun({ text: headings.join(' › '), size: 18 }),
        ],
      }),
    );
  }

  const excerpt = normaliseExcerpt(String(r.text || ''));
  const blocks = excerpt.split(/\n{2,}/);
  for (const block of blocks) {
    const inner = block.split('\n').join(' ').trim();
    if (!inner) continue;
    out.push(
      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: inner })],
      }),
    );
  }

  out.push(
    new Paragraph({
      spacing: { after: 240 },
      children: [
        new ExternalHyperlink({
          link: href,
          children: [new TextRun({ text: 'Open source document ›', style: 'Hyperlink', size: 18 })],
        }),
      ],
    }),
  );

  return out;
};

const buildResultsSection = (
  results: SearchResult[],
  siteOrigin: string,
  dataSource?: string,
): Paragraph[] => {
  const out: Paragraph[] = [];
  out.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: `Search Results (${results.length})` })],
      spacing: { before: 360, after: 120 },
    }),
  );
  results.forEach((r, idx) => {
    out.push(...buildResultCard(r, idx, siteOrigin, dataSource));
  });
  return out;
};

// ---------------------------------------------------------------------------
// Public entry points
// ---------------------------------------------------------------------------

/** Build the in-memory `docx` Document for the given export options. Exposed
 *  separately from {@link exportResultsToDocxBlob} to allow unit tests to
 *  introspect the document structure without packing a Blob. */
export const buildExportDocument = (opts: ExportOptions): Document => {
  const now = (opts.now ?? (() => new Date()))();
  const siteOrigin = opts.siteOrigin || 'https://evidencelab.ai';

  const body: Paragraph[] = [
    ...buildCoverParagraphs(opts, now),
    ...buildSummarySection(opts.aiSummary ?? ''),
    ...buildResultsSection(opts.results, siteOrigin, opts.dataSource),
  ];

  return new Document({
    creator: 'Evidence Lab',
    title: `Evidence Lab Search — ${opts.query}`,
    description: `Export of ${opts.results.length} search results` +
      (opts.aiSummary ? ' and the AI summary' : ''),
    numbering: {
      config: [
        {
          reference: 'summary-ordered',
          levels: [
            {
              level: 0,
              format: LevelFormat.DECIMAL,
              text: '%1.',
              alignment: AlignmentType.START,
              style: { paragraph: { indent: { left: convertInchesToTwip(0.4), hanging: convertInchesToTwip(0.2) } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: { page: { margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } } },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new TextRun({
                    children: [
                      'Evidence Lab — page ',
                      PageNumber.CURRENT,
                      ' of ',
                      PageNumber.TOTAL_PAGES,
                    ],
                    size: 16,
                    color: '888888',
                  }),
                ],
              }),
            ],
          }),
        },
        children: body,
      },
    ],
  });
};

/** Serialise the export to a Word-compatible Blob. */
export const exportResultsToDocxBlob = async (opts: ExportOptions): Promise<Blob> => {
  const doc = buildExportDocument(opts);
  const blob = await Packer.toBlob(doc);
  // docx's Packer returns a Blob with the generic zip MIME — override so
  // consumers (and tests) see the Word-specific type.
  return new Blob([blob], { type: DOCX_MIME });
};

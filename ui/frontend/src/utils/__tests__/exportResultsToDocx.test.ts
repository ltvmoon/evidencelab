/**
 * Unit tests for the Word export utility.
 *
 * Strategy:
 *   - Pure helpers (filename, link resolution, markdown→paragraphs) are tested
 *     directly for determinism.
 *   - The end-to-end Blob path is exercised by generating a real docx, unzipping
 *     it via jszip (a transitive dep of the `docx` package), and asserting that
 *     word/document.xml contains the query, AI summary content, every result's
 *     title, the FULL excerpt, and working hyperlinks.
 */
import JSZip from 'jszip';
import { Paragraph } from 'docx';

import {
  DOCX_MIME,
  buildExportFilename,
  exportResultsToDocxBlob,
  markdownToParagraphs,
  resolveResultLink,
} from '../exportResultsToDocx';
import type { SearchResult } from '../../types/api';

const makeResult = (overrides: Partial<SearchResult> = {}): SearchResult => ({
  chunk_id: 'c1',
  doc_id: 'd1',
  text: 'The impact of climate related shocks and stresses on food security in Bangladesh could be severe. Smallholder farmers are disproportionately affected.',
  page_num: 12,
  headings: ['Executive Summary', 'Food Security'],
  score: 0.876,
  title: 'Sample Evaluation Report',
  organization: 'UNDP',
  year: '2023',
  metadata: {},
  ...overrides,
});

describe('buildExportFilename', () => {
  const FIXED = new Date('2026-04-22T09:05:00.000Z');
  test('slugifies query and appends YYYYMMDD-HHMM stamp', () => {
    const name = buildExportFilename('Impact of Climate Change on Food Security!', FIXED);
    expect(name).toMatch(/^evidencelab-search-impact-of-climate-change-on-food-security-\d{8}-\d{4}\.docx$/);
  });
  test('handles empty query with a sensible default', () => {
    const name = buildExportFilename('   ', FIXED);
    expect(name).toMatch(/^evidencelab-search-search-\d{8}-\d{4}\.docx$/);
  });
  test('caps the slug length', () => {
    const longQuery = 'a'.repeat(200);
    const name = buildExportFilename(longQuery, FIXED);
    const slugPart = name.split('-').slice(2, -2).join('-');
    expect(slugPart.length).toBeLessThanOrEqual(60);
  });
});

describe('resolveResultLink', () => {
  test('prefers a top-level pdf_url when present', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: 'https://example.org/reports/r1.pdf' }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/reports/r1.pdf');
  });
  test('falls back to metadata.pdf_url', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: undefined, metadata: { pdf_url: 'https://example.org/meta.pdf' } }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/meta.pdf');
  });
  test('falls back to a canonical deep-link with page anchor', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: undefined, report_url: undefined, doc_id: 'abc123', page_num: 7 }),
      'https://evidencelab.ai',
      'uneg',
    );
    expect(link).toBe('https://evidencelab.ai/document/abc123?data_source=uneg#page=7');
  });
  test('handles a trailing slash in the site origin', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: undefined, report_url: undefined, doc_id: 'abc', page_num: 1 }),
      'https://evidencelab.ai/',
      'uneg',
    );
    expect(link.startsWith('https://evidencelab.ai/document/')).toBe(true);
    expect(link).not.toMatch(/evidencelab\.ai\/\/document/);
  });
});

describe('markdownToParagraphs', () => {
  test('emits one paragraph per heading / bullet / paragraph block', () => {
    // 1 H2 + 1 H3 + 1 paragraph + 2 bullets = 5 Paragraph nodes
    const paragraphs = markdownToParagraphs(
      '## Alpha\n\n### Beta\n\nIntro paragraph with a sentence.\n\n- point one\n- point two',
    );
    expect(paragraphs).toHaveLength(5);
    // Every element is a Paragraph instance (rather than, e.g., undefined).
    for (const p of paragraphs) expect(p).toBeInstanceOf(Paragraph);
  });
  test('tolerates empty input', () => {
    expect(markdownToParagraphs('')).toEqual([]);
  });
  test('collapses consecutive blank lines into a single paragraph break', () => {
    const paragraphs = markdownToParagraphs('Line one\n\n\n\nLine two');
    expect(paragraphs).toHaveLength(2);
  });
});

describe('exportResultsToDocxBlob', () => {
  const FIXED = new Date('2026-04-22T09:05:00.000Z');
  const baseOpts = {
    query: 'impact of climate change on food security',
    aiSummary: '## Summary\n\nClimate change disrupts food systems. **Smallholders** bear the brunt.',
    dataSource: 'UN Humanitarian Evaluation Reports',
    now: () => FIXED,
    results: [
      makeResult({
        chunk_id: 'c1',
        doc_id: 'doc-1',
        title: 'Bangladesh Nutrition Evaluation',
        organization: 'UNICEF',
        year: '2021',
        text: 'Climate change effects reduce rice productivity across rural Bangladesh. Smallholder resilience is limited.',
        pdf_url: 'https://example.org/reports/bangladesh.pdf',
        page_num: 42,
      }),
      makeResult({
        chunk_id: 'c2',
        doc_id: 'doc-2',
        title: 'Sahel Food Security Review',
        organization: 'WFP',
        year: '2022',
        text: 'Recurrent droughts compressed the rain-fed cropping window and triggered pastoralist displacement.',
        pdf_url: undefined,
        page_num: 9,
      }),
    ],
  };

  const unzip = async (blob: Blob): Promise<string> => {
    const zip = await JSZip.loadAsync(await blob.arrayBuffer());
    const doc = zip.file('word/document.xml');
    if (!doc) throw new Error('word/document.xml missing');
    return doc.async('string');
  };

  test('produces a non-empty Blob with Word MIME', async () => {
    const blob = await exportResultsToDocxBlob(baseOpts);
    expect(blob.type).toBe(DOCX_MIME);
    expect(blob.size).toBeGreaterThan(2_000);
  });

  test('docx contents include the query, AI summary, and every result title', async () => {
    const xml = await unzip(await exportResultsToDocxBlob(baseOpts));
    expect(xml).toContain('Evidence Lab');
    expect(xml).toContain('impact of climate change on food security');
    // AI summary heading + body snippet
    expect(xml).toContain('Summary');
    expect(xml).toContain('Smallholders'); // bold run
    expect(xml).toContain('Climate change disrupts food systems.');
    // Result titles
    expect(xml).toContain('Bangladesh Nutrition Evaluation');
    expect(xml).toContain('Sahel Food Security Review');
    // Metadata lines
    expect(xml).toContain('UNICEF');
    expect(xml).toContain('p. 42');
  });

  test('full excerpts are preserved (no truncation)', async () => {
    const longExcerpt =
      'Paragraph one sentence one. Paragraph one sentence two — with an em-dash and footnote [^7].' +
      '\n\n' +
      'Paragraph two covering a totally distinct topic to confirm block separation survives the round trip.';
    const opts = {
      ...baseOpts,
      results: [makeResult({ text: longExcerpt, title: 'Long Excerpt Report' })],
    };
    const xml = await unzip(await exportResultsToDocxBlob(opts));
    expect(xml).toContain('Paragraph one sentence one.');
    expect(xml).toContain('em-dash and footnote [^7]');
    expect(xml).toContain('Paragraph two covering a totally distinct topic');
  });

  test('hyperlinks to pdf_url are embedded in the document relationships', async () => {
    const zip = await JSZip.loadAsync(await (await exportResultsToDocxBlob(baseOpts)).arrayBuffer());
    const rels = zip.file('word/_rels/document.xml.rels');
    expect(rels).not.toBeNull();
    const relsText = await rels!.async('string');
    expect(relsText).toContain('https://example.org/reports/bangladesh.pdf');
    // Fallback link is a canonical deep link to the SPA for results lacking pdf_url
    expect(relsText).toContain('/document/doc-2');
  });

  test('handles zero results gracefully (cover + summary only)', async () => {
    const xml = await unzip(
      await exportResultsToDocxBlob({ ...baseOpts, results: [] }),
    );
    expect(xml).toContain('Search Results (0)');
    expect(xml).toContain('impact of climate change on food security');
  });
});

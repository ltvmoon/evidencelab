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
  buildReferenceGroups,
  exportResultsToDocxBlob,
  extractCitationNumbers,
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
  test('prefers a top-level pdf_url when present and appends page anchor', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: 'https://example.org/reports/r1.pdf', page_num: 12 }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/reports/r1.pdf#page=12');
  });
  test('omits page anchor on pdf_url when page_num is missing', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: 'https://example.org/reports/r1.pdf', page_num: undefined }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/reports/r1.pdf');
  });
  test('replaces an existing #page= fragment instead of duplicating', () => {
    const link = resolveResultLink(
      makeResult({ pdf_url: 'https://example.org/reports/r1.pdf#page=1', page_num: 5 }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/reports/r1.pdf#page=5');
  });
  test('falls back to metadata.pdf_url with page anchor', () => {
    const link = resolveResultLink(
      makeResult({
        pdf_url: undefined,
        metadata: { pdf_url: 'https://example.org/meta.pdf' },
        page_num: 3,
      }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/meta.pdf#page=3');
  });
  test('falls back to report_url with page anchor', () => {
    const link = resolveResultLink(
      makeResult({
        pdf_url: undefined,
        report_url: 'https://example.org/report.html',
        page_num: 9,
      }),
      'https://evidencelab.ai',
    );
    expect(link).toBe('https://example.org/report.html#page=9');
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

describe('extractCitationNumbers', () => {
  test('returns sorted unique numbers', () => {
    expect(extractCitationNumbers('a [3] b [1] c [3] d [2,1]')).toEqual([1, 2, 3]);
  });
  test('handles multi-citation brackets with whitespace', () => {
    expect(extractCitationNumbers('See [1, 4, 7].')).toEqual([1, 4, 7]);
  });
  test('returns [] when no citations present', () => {
    expect(extractCitationNumbers('plain text with no marks')).toEqual([]);
  });
});

describe('buildReferenceGroups', () => {
  test('groups by document title and renumbers in citation order', () => {
    // Mirrors AiSummaryReferences: citations are processed in *sorted
    // numeric* order, then renumbered into that order. So a summary that
    // mentions [2] first but also cites [1] and [3] still walks 1→2→3.
    const results = [
      makeResult({ title: 'Doc A', organization: 'OrgA', year: '2020', page_num: 4 }),
      makeResult({ title: 'Doc B', organization: 'OrgB', year: '2021', page_num: 1 }),
      makeResult({ title: 'Doc A', organization: 'OrgA', year: '2020', page_num: 9 }),
    ];
    const groups = buildReferenceGroups('first [2], then [1] and [3]', results);
    expect(groups).toHaveLength(2);
    // Doc A is the first group encountered (citation [1] → results[0])
    expect(groups[0].title).toBe('Doc A');
    expect(groups[0].refs.map((r) => r.sequential)).toEqual([1, 3]);
    expect(groups[0].refs.map((r) => r.result.page_num)).toEqual([4, 9]);
    expect(groups[1].title).toBe('Doc B');
    expect(groups[1].refs.map((r) => r.sequential)).toEqual([2]);
    expect(groups[1].refs[0].result.page_num).toBe(1);
  });
  test('skips out-of-range citation numbers', () => {
    const results = [makeResult({ title: 'Only Doc' })];
    const groups = buildReferenceGroups('claim [1] then bogus [99]', results);
    expect(groups).toHaveLength(1);
    expect(groups[0].refs).toHaveLength(1);
  });
  test('returns [] when summary has no citations', () => {
    expect(buildReferenceGroups('no marks here', [makeResult()])).toEqual([]);
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
  test('headingShift demotes ATX headings by the given amount', () => {
    const [shifted] = markdownToParagraphs('# Top', 1);
    const [unshifted] = markdownToParagraphs('# Top', 0);
    // The library's HeadingLevel values are opaque strings — assert via the
    // serialised paragraph shape that the heading level differs and is one
    // step lower.
    const shiftedJson = JSON.stringify((shifted as unknown as { properties: unknown }).properties);
    const unshiftedJson = JSON.stringify(
      (unshifted as unknown as { properties: unknown }).properties,
    );
    expect(shiftedJson).toContain('Heading2');
    expect(unshiftedJson).toContain('Heading1');
  });
  test('heading depth is clamped at H6 even with large shift', () => {
    const [p] = markdownToParagraphs('###### Deep', 5);
    const json = JSON.stringify((p as unknown as { properties: unknown }).properties);
    expect(json).toContain('Heading6');
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

  test('default body and heading fonts are configured to match the web app', async () => {
    const zip = await JSZip.loadAsync(await (await exportResultsToDocxBlob(baseOpts)).arrayBuffer());
    const styles = zip.file('word/styles.xml');
    expect(styles).not.toBeNull();
    const text = await styles!.async('string');
    expect(text).toContain('Open Sans');
    expect(text).toContain('Poppins');
  });

  test('PDF hyperlinks include a #page= anchor pointing at the cited page', async () => {
    const zip = await JSZip.loadAsync(await (await exportResultsToDocxBlob(baseOpts)).arrayBuffer());
    const rels = await zip.file('word/_rels/document.xml.rels')!.async('string');
    expect(rels).toContain('https://example.org/reports/bangladesh.pdf#page=42');
  });

  test('renders a References section listing each cited document', async () => {
    const opts = {
      ...baseOpts,
      aiSummary:
        '## Findings\n\nClimate change disrupts food systems [1]. Sahel droughts compound this [2].',
    };
    const xml = await unzip(await exportResultsToDocxBlob(opts));
    expect(xml).toContain('References');
    expect(xml).toContain('Bangladesh Nutrition Evaluation');
    expect(xml).toContain('Sahel Food Security Review');
    expect(xml).toContain('p.42');
    expect(xml).toContain('p.9');
  });

  test('omits References section when the summary has no citations', async () => {
    const opts = {
      ...baseOpts,
      aiSummary: '## Notes\n\nNo bracketed citations in this body.',
    };
    const xml = await unzip(await exportResultsToDocxBlob(opts));
    // Heading text 'References' must not appear in document.xml when the
    // summary cites nothing — keeps short summaries clean.
    expect(xml).not.toContain('>References<');
  });
});

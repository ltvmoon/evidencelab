import { applyDevFixture } from '../useDevFixtureSearch';
import type { SearchResult } from '../../types/api';

const FIXTURE_DATA = {
  results: [{ chunk_id: 'f1', doc_id: 'f1' } as unknown as SearchResult],
  summary: '## Fixture summary',
};

describe('applyDevFixture', () => {
  const baseInput = { query: '', results: [], aiSummary: '', loading: false };

  test('is a no-op when the feature flag is off', () => {
    const out = applyDevFixture({ ...baseInput, query: 'x' }, false, FIXTURE_DATA);
    expect(out.isFixtureActive).toBe(false);
    expect(out.effectiveResults).toBe(baseInput.results);
    expect(out.effectiveAiSummary).toBe(baseInput.aiSummary);
  });

  test('is a no-op when the query is empty', () => {
    const out = applyDevFixture({ ...baseInput, query: '   ' }, true, FIXTURE_DATA);
    expect(out.isFixtureActive).toBe(false);
  });

  test('is a no-op while a real search is in flight', () => {
    const out = applyDevFixture(
      { ...baseInput, query: 'x', loading: true },
      true,
      FIXTURE_DATA,
    );
    expect(out.isFixtureActive).toBe(false);
  });

  test('is a no-op if real results already arrived', () => {
    const out = applyDevFixture(
      { ...baseInput, query: 'x', results: [{ chunk_id: 'real' } as unknown as SearchResult] },
      true,
      FIXTURE_DATA,
    );
    expect(out.isFixtureActive).toBe(false);
  });

  test('is a no-op while the fixture data is still loading (data === null)', () => {
    const out = applyDevFixture({ ...baseInput, query: 'x' }, true, null);
    expect(out.isFixtureActive).toBe(false);
    expect(out.effectiveResults).toBe(baseInput.results);
  });

  test('activates when flag is on, query present, no real data, and fixture loaded', () => {
    const out = applyDevFixture({ ...baseInput, query: 'climate' }, true, FIXTURE_DATA);
    expect(out.isFixtureActive).toBe(true);
    expect(out.effectiveResults).toBe(FIXTURE_DATA.results);
    expect(out.effectiveAiSummary).toBe(FIXTURE_DATA.summary);
  });
});

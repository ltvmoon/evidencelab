/**
 * Dev-only hook that substitutes a realistic sample search + AI summary
 * when REACT_APP_DEV_FIXTURES=true is set at build/start time.
 *
 * The fixture data is loaded via a *dynamic import* so webpack can emit it
 * as a separate chunk. In production builds, REACT_APP_DEV_FIXTURES is
 * undefined, the `if` below short-circuits, and Terser eliminates the
 * dynamic `import()` — the fixture bytes never ship to end-users.
 *
 * No effect in production in any scenario: the hook becomes a passthrough
 * that returns `input.results` / `input.aiSummary` exactly as received.
 */
import { useEffect, useMemo, useState } from 'react';
import type { SearchResult } from '../types/api';

export interface DevFixtureInput {
  query: string;
  results: SearchResult[];
  aiSummary: string;
  loading: boolean;
}

export interface DevFixtureOutput {
  /** Results the component should render — identical to `input.results` when
   *  the fixture is inactive. */
  effectiveResults: SearchResult[];
  /** AI summary the component should render — identical to `input.aiSummary`
   *  when the fixture is inactive. */
  effectiveAiSummary: string;
  /** True when the hook substituted fixture data — callers can use this to
   *  render a small indicator in dev, e.g. "dev-fixture". */
  isFixtureActive: boolean;
}

interface FixtureData {
  results: SearchResult[];
  summary: string;
}

/** Core activation rule — the fixture only kicks in when every condition
 *  holds: the flag is on, the user typed a non-blank query, there are no
 *  real results yet, and no request is in flight. */
const shouldActivate = (
  input: DevFixtureInput,
  enabled: boolean,
  dataLoaded: boolean,
): boolean =>
  enabled &&
  dataLoaded &&
  input.query.trim().length > 0 &&
  input.results.length === 0 &&
  !input.loading;

/** Pure form — exported for unit tests that need to assert the substitution
 *  logic without involving React or a dynamic import. Callers supply the
 *  fixture data directly. */
export const applyDevFixture = (
  input: DevFixtureInput,
  enabled: boolean,
  data: FixtureData | null,
): DevFixtureOutput => {
  if (!shouldActivate(input, enabled, data !== null)) {
    return {
      effectiveResults: input.results,
      effectiveAiSummary: input.aiSummary,
      isFixtureActive: false,
    };
  }
  return {
    effectiveResults: data!.results,
    effectiveAiSummary: data!.summary,
    isFixtureActive: true,
  };
};

export const useDevFixtureSearch = (
  input: DevFixtureInput,
): DevFixtureOutput => {
  const enabled = process.env.REACT_APP_DEV_FIXTURES === 'true';
  const [data, setData] = useState<FixtureData | null>(null);

  useEffect(() => {
    // Dead-code-eliminated in prod: `enabled` is a build-time literal `false`
    // when REACT_APP_DEV_FIXTURES is unset, so Terser strips the body below
    // and webpack drops the dynamic-import chunk from the output.
    if (!enabled || data !== null) return;
    let cancelled = false;
    void import('./devFixtureData').then((mod) => {
      if (cancelled) return;
      setData({ results: mod.FIXTURE_RESULTS, summary: mod.AI_SUMMARY_FIXTURE });
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, data]);

  return useMemo(
    () => applyDevFixture(input, enabled, data),
    // Memoise on every field of `input` so the output remains stable as long
    // as the caller's inputs do.
    [enabled, data, input.query, input.results, input.aiSummary, input.loading],
  );
};

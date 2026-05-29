/**
 * Dev-fixture payload — imported ONLY via the dynamic `import('./devFixtureData')`
 * call inside `useDevFixtureSearch`. Keeping the heavy JSON + summary in a
 * dedicated module lets webpack emit them as a separate chunk so they don't
 * ship to production users when REACT_APP_DEV_FIXTURES is not set.
 *
 * Any static import of this file will defeat that split — don't introduce one.
 */
import type { SearchResult } from '../types/api';
import rawFixture from './searchResults.fixture.json';
import { AI_SUMMARY_FIXTURE } from './aiSummary.fixture';

export const FIXTURE_RESULTS = rawFixture as unknown as SearchResult[];
export { AI_SUMMARY_FIXTURE };

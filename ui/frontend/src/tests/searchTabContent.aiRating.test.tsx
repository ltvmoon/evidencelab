import React from 'react';
import { act, render } from '@testing-library/react';

import { SearchTabContent } from '../components/app/SearchTabContent';
import { DrilldownNode, SearchResult } from '../types/api';

// Capture the props the AiSummaryPanel receives so we can assert on
// `ratingScore`, which is what the rating star component renders from.
let mockAiSummaryProps: Record<string, unknown> | null = null;
jest.mock('../components/AiSummaryPanel', () => ({
  AiSummaryPanel: (props: Record<string, unknown>) => {
    mockAiSummaryProps = props;
    return <div data-testid="ai-summary-panel" />;
  },
}));

jest.mock('../components/filters/FiltersPanel', () => ({
  FiltersPanel: () => <div>Filters Panel</div>,
}));

jest.mock('../components/SearchResultsList', () => ({
  SearchResultsList: () => <div data-testid="results-list" />,
}));

// Capture RatingModal props so a test can fire its onSubmit and observe the
// itemId that gets sent to submitRating.
let mockRatingModalProps: Record<string, unknown> | null = null;
jest.mock('../components/ratings/RatingModal', () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    mockRatingModalProps = props;
    return <div data-testid="rating-modal" />;
  },
}));

// useAuth must report authenticated so SearchTabContent enables the
// `ai_summary` ratings query and passes `isAuthenticated` down.
jest.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: true, user: { id: 'u-1' } }),
}));

// Controlled useRatings: return a Map with one rating for the root summary
// (item_id=null/'') and one for a drilldown node ('dd-1'). Capture the
// last submitRating call so we can assert the itemId argument.
const mockSubmitRating = jest.fn(async (params: Record<string, unknown>) => ({
  id: 'new-rating',
  ...params,
}));

jest.mock('../hooks/useRatings', () => {
  const buildMap = () => {
    const map = new Map<string, Record<string, unknown>>();
    map.set('', { id: 'r-root', item_id: null, score: 5, comment: 'root review' });
    map.set('dd-1', { id: 'r-dd1', item_id: 'dd-1', score: 3, comment: 'drilldown review' });
    return map;
  };
  return {
    __esModule: true,
    useRatings: ({ ratingType }: { ratingType: string }) => ({
      ratings: ratingType === 'ai_summary' ? buildMap() : new Map(),
      loading: false,
      submitRating: mockSubmitRating,
      deleteRating: jest.fn(),
      refresh: jest.fn(),
    }),
    default: ({ ratingType }: { ratingType: string }) => ({
      ratings: ratingType === 'ai_summary' ? buildMap() : new Map(),
      loading: false,
      submitRating: mockSubmitRating,
      deleteRating: jest.fn(),
      refresh: jest.fn(),
    }),
  };
});

const buildResult = (overrides: Partial<SearchResult> = {}): SearchResult => ({
  chunk_id: 'chunk-1',
  doc_id: 'doc-1',
  text: 'Sample text',
  page_num: 1,
  headings: [],
  score: 0.9,
  title: 'Report A',
  organization: 'UNICEF',
  year: '2023',
  metadata: {},
  ...overrides,
});

const buildTree = (currentId: string): DrilldownNode => ({
  id: 'root',
  label: 'root',
  summary: 'root summary',
  prompt: '',
  results: [],
  translatedText: null,
  translatedLang: null,
  expanded: true,
  children: currentId === 'dd-1' || currentId === 'dd-2' ? [
    {
      id: currentId,
      label: 'child',
      summary: 'child summary',
      prompt: '',
      results: [],
      translatedText: null,
      translatedLang: null,
      expanded: true,
      children: [],
    },
  ] : [],
});

const baseProps = {
  filtersExpanded: false,
  activeFiltersCount: 0,
  onToggleFiltersExpanded: jest.fn(),
  onClearFilters: jest.fn(),
  facets: null,
  selectedFilters: {},
  collapsedFilters: new Set<string>(),
  expandedFilterLists: new Set<string>(),
  filterSearchTerms: {},
  titleSearchResults: [],
  facetSearchResults: {},
  onRemoveFilter: jest.fn(),
  onToggleFilter: jest.fn(),
  onFilterSearchTermChange: jest.fn(),
  onToggleFilterListExpansion: jest.fn(),
  onFilterValuesChange: jest.fn(),
  searchDenseWeight: 0.8,
  onSearchDenseWeightChange: jest.fn(),
  keywordBoostShortQueries: true,
  onKeywordBoostChange: jest.fn(),
  semanticHighlighting: true,
  onSemanticHighlightingChange: jest.fn(),
  minScore: 0,
  maxScore: 1,
  onMinScoreChange: jest.fn(),
  autoMinScore: false,
  onAutoMinScoreToggle: jest.fn(),
  rerankEnabled: false,
  onRerankToggle: jest.fn(),
  recencyBoostEnabled: false,
  onRecencyBoostToggle: jest.fn(),
  recencyWeight: 0.15,
  onRecencyWeightChange: jest.fn(),
  recencyScaleDays: 365,
  onRecencyScaleDaysChange: jest.fn(),
  minChunkSize: 100,
  onMinChunkSizeChange: jest.fn(),
  sectionTypes: [] as string[],
  onSectionTypesChange: jest.fn(),
  deduplicateEnabled: false,
  onDeduplicateToggle: jest.fn(),
  aiSummaryEnabled: true,
  aiSummaryCollapsed: false,
  aiSummaryExpanded: true,
  aiSummaryLoading: false,
  aiSummary: 'Some AI summary text',
  aiSummaryResults: [] as SearchResult[],
  aiPrompt: '',
  showPromptModal: false,
  selectedDomain: 'uneg',
  results: [buildResult()] as SearchResult[],
  loading: false,
  query: 'test',
  selectedDoc: null,
  onResultClick: jest.fn(),
  onOpenPrompt: jest.fn(),
  onClosePrompt: jest.fn(),
  onToggleCollapsed: jest.fn(),
  onToggleExpanded: jest.fn(),
  onOpenMetadata: jest.fn(),
  onLanguageChange: jest.fn(),
  searchId: 'search-123',
};

describe('SearchTabContent AI summary rating scoping', () => {
  beforeEach(() => {
    mockAiSummaryProps = null;
    mockRatingModalProps = null;
    mockSubmitRating.mockClear();
    window.history.replaceState(null, '', '/');
  });

  test('shows the root summary rating when no drilldown is active', () => {
    render(
      <SearchTabContent
        {...baseProps}
        aiDrilldownTree={null}
        aiDrilldownCurrentNodeId={null}
      />,
    );
    expect(mockAiSummaryProps).not.toBeNull();
    expect(mockAiSummaryProps!.ratingScore).toBe(5);
  });

  test('shows the drilldown node rating when drilled into a child', () => {
    render(
      <SearchTabContent
        {...baseProps}
        aiDrilldownTree={buildTree('dd-1')}
        aiDrilldownCurrentNodeId="dd-1"
      />,
    );
    expect(mockAiSummaryProps!.ratingScore).toBe(3);
  });

  test('shows score 0 for a drilldown node that has not been rated yet', () => {
    render(
      <SearchTabContent
        {...baseProps}
        aiDrilldownTree={buildTree('dd-2')}
        aiDrilldownCurrentNodeId="dd-2"
      />,
    );
    expect(mockAiSummaryProps!.ratingScore).toBe(0);
  });

  test('submit uses the drilldown node id as item_id when drilled down', () => {
    render(
      <SearchTabContent
        {...baseProps}
        aiDrilldownTree={buildTree('dd-2')}
        aiDrilldownCurrentNodeId="dd-2"
      />,
    );
    act(() => {
      (mockAiSummaryProps!.onRequestRatingModal as (s: number) => void)(4);
    });
    expect(mockRatingModalProps).not.toBeNull();
    act(() => {
      (mockRatingModalProps!.onSubmit as (s: number, c: string) => void)(4, 'good');
    });
    expect(mockSubmitRating).toHaveBeenCalledTimes(1);
    const call = mockSubmitRating.mock.calls[0][0];
    expect(call.ratingType).toBe('ai_summary');
    expect(call.referenceId).toBe('search-123');
    expect(call.itemId).toBe('dd-2');
    expect(call.score).toBe(4);
  });

  test('submit omits item_id for the root summary (back-compat)', () => {
    render(
      <SearchTabContent
        {...baseProps}
        aiDrilldownTree={null}
        aiDrilldownCurrentNodeId={null}
      />,
    );
    act(() => {
      (mockAiSummaryProps!.onRequestRatingModal as (s: number) => void)(2);
    });
    act(() => {
      (mockRatingModalProps!.onSubmit as (s: number, c: string) => void)(2, '');
    });
    const call = mockSubmitRating.mock.calls[0][0];
    expect(call.itemId).toBeUndefined();
  });
});

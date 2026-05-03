import React from 'react';
import type { SearchResult } from '../types/api';
import { ExportResultsButton } from './ExportResultsButton';

interface ResultsHeaderRowProps {
  /** Effective results (may be fixture data in dev mode) used to drive both
   *  the visibility gate and the export payload. */
  results: SearchResult[];
  /** User's query — forwarded into the exported docx. */
  query: string;
  /** AI summary text, if any. */
  aiSummary?: string;
  /** Dataset name for the exported docx cover. */
  dataSource?: string;
  /** When true, render a small "dev fixture" badge next to the heading. */
  showFixtureBadge?: boolean;
}

/**
 * Renders the "Search Results" heading row above the list of results,
 * including the Export-to-Word button (right-aligned on the same line).
 *
 * Extracted as its own component (rather than inlined in SearchTabContent)
 * so the parent's cognitive complexity stays below the repo's configured
 * sonarjs ceiling.
 */
export const ResultsHeaderRow: React.FC<ResultsHeaderRowProps> = ({
  results,
  query,
  aiSummary,
  dataSource,
  showFixtureBadge,
}) => {
  if (results.length === 0) return null;
  return (
    <div className="search-results-heading-row">
      <h3 className="search-results-heading">
        Search Results
        {showFixtureBadge ? (
          <span className="dev-fixture-badge" title="Showing local fixture data">
            dev fixture
          </span>
        ) : null}
      </h3>
      <ExportResultsButton
        results={results}
        query={query}
        aiSummary={aiSummary}
        dataSource={dataSource}
        className="search-results-export"
      />
    </div>
  );
};

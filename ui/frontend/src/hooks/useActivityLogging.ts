import { useCallback, useRef } from 'react';
import axios from 'axios';
import API_BASE_URL from '../config';
import type { SearchResult } from '../types/api';

/**
 * Hook for fire-and-forget logging of search activity.
 *
 * Usage:
 *   const { logSearch, updateSummary } = useActivityLogging();
 *   // After search completes:
 *   logSearch(searchId, query, filters, results);
 *   // After AI summary stream finishes:
 *   updateSummary(searchId, summaryText);
 */
export function useActivityLogging() {
  // Track search IDs that have been logged so we don't double-log
  const loggedSearchIds = useRef(new Set<string>());

  /**
   * Log a search event. Called once after each search completes.
   * Sends a lean version of results (chunk_id, doc_id, title, score only).
   */
  const logSearch = useCallback(
    (
      searchId: string,
      query: string,
      filters: Record<string, any> | null,
      results: SearchResult[],
    ) => {
      if (loggedSearchIds.current.has(searchId)) return;
      loggedSearchIds.current.add(searchId);

      // Trim the results to a lean payload (first page, key fields only)
      const leanResults = results.slice(0, 50).map((r) => ({
        chunk_id: r.chunk_id,
        doc_id: r.doc_id,
        title: r.title,
        score: r.score,
      }));

      // Fire-and-forget — don't await, don't block
      axios
        .post(`${API_BASE_URL}/activity/`, {
          search_id: searchId,
          query,
          filters: filters && Object.keys(filters).length > 0 ? filters : null,
          search_results: leanResults,
          url: window.location.href,
        })
        .catch((err) => {
          // Silently fail — user may not be authenticated or activity logging may be unavailable
          console.debug('Activity logging failed (non-critical):', err?.message);
        });
    },
    [],
  );

  /**
   * Append / update the AI summary text on a previously logged activity record.
   * Called after the AI summary stream completes.
   */
  const updateSummary = useCallback(
    (searchId: string, summaryText: string) => {
      if (!summaryText || !searchId) return;

      axios
        .patch(`${API_BASE_URL}/activity/${searchId}/summary`, {
          ai_summary: summaryText,
        })
        .catch((err) => {
          console.debug('Activity summary update failed (non-critical):', err?.message);
        });
    },
    [],
  );

  return { logSearch, updateSummary };
}

export default useActivityLogging;

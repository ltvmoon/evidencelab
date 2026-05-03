import React, { useCallback, useState } from 'react';
import { saveAs } from 'file-saver';
import type { SearchResult } from '../types/api';
import {
  buildExportFilename,
  exportResultsToDocxBlob,
} from '../utils/exportResultsToDocx';

interface ExportResultsButtonProps {
  /** Live search results currently on screen. */
  results: SearchResult[];
  /** User's query — used in the title + filename. */
  query: string;
  /** Rendered AI summary markdown, if any. Optional. */
  aiSummary?: string;
  /** Human-readable dataset name (shown on the cover). */
  dataSource?: string;
  /** Optional className so parents can position the button. */
  className?: string;
}

/**
 * Button that generates a Word (.docx) export of the current AI summary
 * and search results and triggers a browser download.
 *
 * The generation is fully client-side — it reads from the props the
 * component was handed, so what you see on screen is what gets exported.
 */
export const ExportResultsButton: React.FC<ExportResultsButtonProps> = ({
  results,
  query,
  aiSummary,
  dataSource,
  className,
}) => {
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const onClick = useCallback(async () => {
    if (busy || results.length === 0) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const blob = await exportResultsToDocxBlob({
        query,
        aiSummary,
        results,
        dataSource,
        // Use the current deployment's origin for fallback deep-links in the
        // docx. Falls back to the hardcoded prod host only when window is
        // unavailable (e.g. during server-side rendering or unit tests).
        siteOrigin:
          typeof window !== 'undefined' && window.location
            ? window.location.origin
            : undefined,
      });
      saveAs(blob, buildExportFilename(query, new Date()));
    } catch (err) {
      // Surface the error in-UI so the user knows the download failed —
      // silent failures are worse than a visible error message here.
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      console.error('Export to Word failed:', err);
    } finally {
      setBusy(false);
    }
  }, [busy, results, query, aiSummary, dataSource]);

  const disabled = busy || results.length === 0;
  return (
    <div className={className}>
      <button
        type="button"
        className="export-results-button"
        onClick={onClick}
        disabled={disabled}
        title={
          results.length === 0
            ? 'Run a search first'
            : 'Export the AI summary and search results as a Word document'
        }
        aria-label="Export search results to Word"
      >
        {busy ? (
          <span>Preparing Word document…</span>
        ) : (
          <span>
            <span aria-hidden="true" style={{ marginRight: 6 }}>↓</span>
            Export to Word
          </span>
        )}
      </button>
      {errorMsg ? (
        <span className="export-results-error" role="alert">
          {' '}Could not export: {errorMsg}
        </span>
      ) : null}
    </div>
  );
};

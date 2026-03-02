import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config';

interface RatingRow {
  id: string;
  user_id: string;
  user_email: string | null;
  user_display_name: string | null;
  rating_type: string;
  reference_id: string;
  item_id: string | null;
  score: number;
  comment: string | null;
  context: Record<string, any> | null;
  url: string | null;
  created_at: string;
  updated_at: string;
}

interface RatingsResponse {
  items: RatingRow[];
  total: number;
  page: number;
  page_size: number;
}

const RATING_TYPES = ['all', 'search_result', 'ai_summary', 'doc_summary', 'taxonomy'];

const formatDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
};

const renderStars = (score: number) => {
  return '★'.repeat(score) + '☆'.repeat(5 - score);
};

/** Truncate text with ellipsis */
const truncate = (text: string, max: number) =>
  text.length > max ? text.slice(0, max) + '…' : text;

// ---------------------------------------------------------------------------
// Context detail components
// ---------------------------------------------------------------------------

/** Collapsible results snapshot list */
const ResultsSnapshotList: React.FC<{ results: any[] }> = ({ results }) => {
  const [expanded, setExpanded] = useState(false);
  if (!results || results.length === 0) return null;

  const visible = expanded ? results : results.slice(0, 2);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontWeight: 600, fontSize: '0.78rem', color: '#555', marginBottom: 4 }}>
        Search Results ({results.length})
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {visible.map((r: any, i: number) => (
          <div
            key={i}
            style={{
              background: '#f9fafb',
              borderRadius: 4,
              padding: '6px 8px',
              fontSize: '0.78rem',
              border: '1px solid #e5e7eb',
            }}
          >
            <div style={{ fontWeight: 600, color: '#1a1f36' }}>
              {r.title || 'Untitled'}
            </div>
            <div style={{ color: '#6b7280', marginTop: 2 }}>
              <span>Doc: {r.doc_id || '-'}</span>
              <span style={{ margin: '0 6px' }}>|</span>
              <span>Chunk: {r.chunk_id || '-'}</span>
              {r.page_num && (
                <>
                  <span style={{ margin: '0 6px' }}>|</span>
                  <span>Page {r.page_num}</span>
                </>
              )}
              {r.score != null && (
                <>
                  <span style={{ margin: '0 6px' }}>|</span>
                  <span>Score: {typeof r.score === 'number' ? r.score.toFixed(3) : r.score}</span>
                </>
              )}
            </div>
            {r.chunk_text && (
              <div
                style={{
                  marginTop: 4,
                  color: '#4a5568',
                  fontStyle: 'italic',
                  whiteSpace: 'pre-wrap',
                  maxHeight: 60,
                  overflow: 'hidden',
                }}
              >
                {truncate(r.chunk_text, 200)}
              </div>
            )}
          </div>
        ))}
      </div>
      {results.length > 2 && (
        <button
          onClick={() => setExpanded((prev) => !prev)}
          style={{
            marginTop: 4,
            fontSize: '0.76rem',
            color: '#1a73e8',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {expanded ? 'Show less' : `Show ${results.length - 2} more…`}
        </button>
      )}
    </div>
  );
};

/** Render the AI summary text */
const AiSummaryBlock: React.FC<{ summary: string }> = ({ summary }) => {
  const [expanded, setExpanded] = useState(false);
  if (!summary) return null;

  const isLong = summary.length > 300;
  const display = expanded || !isLong ? summary : truncate(summary, 300);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontWeight: 600, fontSize: '0.78rem', color: '#555', marginBottom: 4 }}>
        AI Summary
      </div>
      <div
        style={{
          fontSize: '0.78rem',
          color: '#374151',
          background: '#f0f9ff',
          borderRadius: 4,
          padding: '6px 8px',
          border: '1px solid #bae6fd',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {display}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded((prev) => !prev)}
          style={{
            marginTop: 2,
            fontSize: '0.76rem',
            color: '#1a73e8',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {expanded ? 'Collapse' : 'Show full summary'}
        </button>
      )}
    </div>
  );
};

/** Display key-value context fields */
const ContextFields: React.FC<{ context: Record<string, any>; exclude?: string[] }> = ({
  context,
  exclude = [],
}) => {
  const skip = new Set([...exclude, 'ai_summary', 'results_snapshot', 'summary']);
  const entries = Object.entries(context).filter(
    ([key]) => !skip.has(key) && context[key] != null && context[key] !== ''
  );
  if (entries.length === 0) return null;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'auto 1fr',
        gap: '2px 10px',
        fontSize: '0.78rem',
        marginTop: 8,
      }}
    >
      {entries.map(([key, val]) => (
        <React.Fragment key={key}>
          <span style={{ color: '#6b7280', fontWeight: 500, whiteSpace: 'nowrap' }}>
            {key.replace(/_/g, ' ')}:
          </span>
          <span style={{ color: '#374151', wordBreak: 'break-all' }}>
            {typeof val === 'object' ? JSON.stringify(val) : String(val)}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
};

/** Full context panel for a rating row */
const RatingContextPanel: React.FC<{ rating: RatingRow }> = ({ rating }) => {
  const ctx = rating.context;
  if (!ctx || Object.keys(ctx).length === 0) {
    return <span style={{ color: '#999', fontSize: '0.78rem' }}>No context data</span>;
  }

  const aiSummary = ctx.ai_summary || ctx.summary || '';
  const resultsSnapshot = ctx.results_snapshot;

  return (
    <div>
      <ContextFields context={ctx} />
      {aiSummary && <AiSummaryBlock summary={aiSummary} />}
      {resultsSnapshot && Array.isArray(resultsSnapshot) && (
        <ResultsSnapshotList results={resultsSnapshot} />
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const RatingsManager: React.FC = () => {
  const [ratings, setRatings] = useState<RatingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [filterType, setFilterType] = useState('all');
  const [exporting, setExporting] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const fetchRatings = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        order,
      };
      if (search) params.search = search;
      if (filterType !== 'all') params.rating_type = filterType;

      const resp = await axios.get<RatingsResponse>(`${API_BASE_URL}/ratings/all`, { params });
      setRatings(resp.data.items);
      setTotal(resp.data.total);
    } catch {
      setError('Failed to load ratings');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, sortBy, order, filterType]);

  useEffect(() => {
    fetchRatings();
  }, [fetchRatings]);

  // Collapse expanded rows on page change
  useEffect(() => {
    setExpandedRows(new Set());
  }, [page, filterType, search, sortBy, order]);

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      setOrder('desc');
    }
    setPage(1);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params: Record<string, string> = {};
      if (filterType !== 'all') params.rating_type = filterType;
      const resp = await axios.get<Blob>(`${API_BASE_URL}/ratings/export`, {
        params,
        responseType: 'blob',
      });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ratings_export.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError('Export failed');
    } finally {
      setExporting(false);
    }
  };

  const sortIndicator = (col: string) => {
    if (sortBy !== col) return '';
    return order === 'asc' ? ' ▲' : ' ▼';
  };

  const hasContext = (r: RatingRow) => r.context && Object.keys(r.context).length > 0;

  return (
    <div className="admin-section">
      {error && (
        <div className="auth-error">
          {error}
          <button className="auth-error-dismiss" onClick={() => setError('')}>&times;</button>
        </div>
      )}

      <div className="admin-controls" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            placeholder="Search by email, reference, or comment..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="admin-search-input"
            style={{ minWidth: '250px', padding: '0.4rem 0.6rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.85rem' }}
          />
          <button type="submit" className="btn-sm" style={{ padding: '0.4rem 0.8rem' }}>
            Search
          </button>
        </form>

        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
          style={{ padding: '0.4rem 0.6rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.85rem' }}
        >
          {RATING_TYPES.map((t) => (
            <option key={t} value={t}>
              {t === 'all' ? 'All Types' : t.replace('_', ' ')}
            </option>
          ))}
        </select>

        <button
          className="admin-download-button"
          onClick={handleExport}
          disabled={exporting}
          style={{ marginLeft: 'auto' }}
        >
          <span className="admin-download-icon" aria-hidden="true">
            <svg viewBox="0 0 20 20" focusable="false">
              <path
                d="M10 2a1 1 0 0 1 1 1v7.59l2.3-2.3a1 1 0 1 1 1.4 1.42l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.42l2.3 2.3V3a1 1 0 0 1 1-1zm-6 12a1 1 0 0 1 1 1v2h10v-2a1 1 0 1 1 2 0v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1z"
                fill="currentColor"
              />
            </svg>
          </span>
          {exporting ? 'Downloading...' : 'Download Ratings'}
        </button>
      </div>

      <p className="text-muted" style={{ marginBottom: '0.5rem', fontSize: '0.85rem' }}>
        {total} rating{total !== 1 ? 's' : ''} found
      </p>

      {loading ? (
        <div className="admin-loading">Loading ratings...</div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th style={{ width: 30 }}></th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('created_at')}>
                    Date{sortIndicator('created_at')}
                  </th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('user_email')}>
                    User{sortIndicator('user_email')}
                  </th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('rating_type')}>
                    Type{sortIndicator('rating_type')}
                  </th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('score')}>
                    Score{sortIndicator('score')}
                  </th>
                  <th>Comment</th>
                  <th>URL</th>
                </tr>
              </thead>
              <tbody>
                {ratings.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '1.5rem', color: '#888' }}>
                      No ratings found
                    </td>
                  </tr>
                ) : (
                  ratings.map((r) => {
                    const isExpanded = expandedRows.has(r.id);
                    return (
                      <React.Fragment key={r.id}>
                        <tr
                          style={{ cursor: hasContext(r) ? 'pointer' : 'default' }}
                          onClick={() => hasContext(r) && toggleRow(r.id)}
                        >
                          <td style={{ textAlign: 'center', fontSize: '0.82rem', color: '#999', padding: '0.4rem' }}>
                            {hasContext(r) ? (isExpanded ? '▾' : '▸') : ''}
                          </td>
                          <td style={{ whiteSpace: 'nowrap', fontSize: '0.82rem' }}>{formatDate(r.created_at)}</td>
                          <td style={{ fontSize: '0.82rem' }}>{r.user_email || r.user_display_name || '-'}</td>
                          <td style={{ fontSize: '0.82rem' }}>{r.rating_type.replace(/_/g, ' ')}</td>
                          <td style={{ color: '#d4a017', fontSize: '0.9rem', letterSpacing: '1px' }}>{renderStars(r.score)}</td>
                          <td style={{ fontSize: '0.82rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.comment || ''}>
                            {r.comment || '-'}
                          </td>
                          <td style={{ fontSize: '0.78rem', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.url || ''}>
                            {r.url ? (
                              <a
                                href={r.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: '#1a73e8' }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                link
                              </a>
                            ) : '-'}
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr>
                            <td colSpan={7} style={{ background: '#fafbfc', padding: '10px 16px', borderTop: 'none' }}>
                              <RatingContextPanel rating={r} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button
                className="btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                ← Prev
              </button>
              <span style={{ fontSize: '0.85rem' }}>
                Page {page} of {totalPages}
              </span>
              <button
                className="btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default RatingsManager;

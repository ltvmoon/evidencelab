import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config';

interface ActivityRow {
  id: string;
  user_id: string;
  user_email: string | null;
  user_display_name: string | null;
  search_id: string;
  query: string;
  filters: Record<string, any> | null;
  search_results: any[] | null;
  ai_summary: string | null;
  url: string | null;
  has_ratings: boolean;
  created_at: string;
}

interface ActivityResponse {
  items: ActivityRow[];
  total: number;
  page: number;
  page_size: number;
}

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

const truncate = (text: string, maxLen: number) =>
  text.length > maxLen ? text.slice(0, maxLen - 3) + '...' : text;

const ActivityManager: React.FC = () => {
  const [rows, setRows] = useState<ActivityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [exporting, setExporting] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const fetchActivity = useCallback(async () => {
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

      const resp = await axios.get<ActivityResponse>(`${API_BASE_URL}/activity/all`, { params });
      setRows(resp.data.items);
      setTotal(resp.data.total);
    } catch {
      setError('Failed to load activity');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, sortBy, order]);

  useEffect(() => {
    fetchActivity();
  }, [fetchActivity]);

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
      const resp = await axios.get<Blob>(`${API_BASE_URL}/activity/export`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `activity_export.xlsx`;
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

  const getResultCount = (row: ActivityRow): number => {
    if (!row.search_results) return 0;
    if (Array.isArray(row.search_results)) return row.search_results.length;
    return 0;
  };

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
            placeholder="Search by email or query..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="admin-search-input"
            style={{ minWidth: '250px', padding: '0.4rem 0.6rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.85rem' }}
          />
          <button type="submit" className="btn-sm" style={{ padding: '0.4rem 0.8rem' }}>
            Search
          </button>
        </form>

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
          {exporting ? 'Downloading...' : 'Download Activity'}
        </button>
      </div>

      <p className="text-muted" style={{ marginBottom: '0.5rem', fontSize: '0.85rem' }}>
        {total} activit{total !== 1 ? 'ies' : 'y'} found
      </p>

      {loading ? (
        <div className="admin-loading">Loading activity...</div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('created_at')}>
                    Date{sortIndicator('created_at')}
                  </th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('user_email')}>
                    User{sortIndicator('user_email')}
                  </th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('query')}>
                    Query{sortIndicator('query')}
                  </th>
                  <th># Results</th>
                  <th>AI Summary</th>
                  <th>URL</th>
                  <th style={{ cursor: 'pointer', whiteSpace: 'nowrap' }} onClick={() => handleSort('has_ratings')}>
                    Rated{sortIndicator('has_ratings')}
                  </th>
                  <th>Search ID</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '1.5rem', color: '#888' }}>
                      No activity found
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.id}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: '0.82rem' }}>{formatDate(r.created_at)}</td>
                      <td style={{ fontSize: '0.82rem' }}>{r.user_email || r.user_display_name || '-'}</td>
                      <td style={{ fontSize: '0.82rem', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.query}>
                        {r.query}
                      </td>
                      <td style={{ textAlign: 'center', fontSize: '0.82rem' }}>{getResultCount(r)}</td>
                      <td style={{ fontSize: '0.78rem', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.ai_summary || ''}>
                        {r.ai_summary ? truncate(r.ai_summary, 80) : '-'}
                      </td>
                      <td style={{ fontSize: '0.78rem', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.url || ''}>
                        {r.url ? (
                          <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: '#1a73e8' }}>
                            link
                          </a>
                        ) : '-'}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {r.has_ratings ? (
                          <span style={{ color: '#2e7d32' }}>✓</span>
                        ) : (
                          <span style={{ color: '#bbb' }}>–</span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.72rem', maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#888' }} title={r.search_id}>
                        {r.search_id.slice(0, 8)}...
                      </td>
                    </tr>
                  ))
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

export default ActivityManager;

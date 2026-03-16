import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config';
import ConfirmModal from './ConfirmModal';

interface ApiKeyItem {
  id: string;
  label: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  created_by_email: string | null;
  last_used_at: string | null;
}

interface CreatedKey extends ApiKeyItem {
  key: string;
}

const ApiKeyManager: React.FC = () => {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [label, setLabel] = useState('');
  const [creating, setCreating] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<CreatedKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string } | null>(null);

  const fetchKeys = useCallback(async () => {
    try {
      const resp = await axios.get<ApiKeyItem[]>(`${API_BASE_URL}/api-keys/`);
      setKeys(resp.data);
    } catch {
      setError('Failed to load API keys');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim()) return;
    setError('');
    setCreating(true);
    try {
      const resp = await axios.post<CreatedKey>(`${API_BASE_URL}/api-keys/`, { label: label.trim() });
      setGeneratedKey(resp.data);
      setLabel('');
      await fetchKeys();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate API key');
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async () => {
    if (!generatedKey) return;
    try {
      await navigator.clipboard.writeText(generatedKey.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Failed to copy to clipboard');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API_BASE_URL}/api-keys/${deleteTarget.id}`);
      setDeleteTarget(null);
      await fetchKeys();
    } catch (err: any) {
      setDeleteTarget(null);
      setError(err.response?.data?.detail || 'Failed to revoke API key');
    }
  };

  if (loading) return <p>Loading API keys...</p>;

  return (
    <div className="admin-section">
      <h3>API Keys</h3>
      {error && (
        <div className="auth-error" style={{ marginBottom: 12 }}>
          {error}
          <button onClick={() => setError('')} style={{ marginLeft: 8, cursor: 'pointer', border: 'none', background: 'none', fontWeight: 'bold' }}>&times;</button>
        </div>
      )}

      {/* Generate form */}
      <form onSubmit={handleCreate} style={{ display: 'flex', gap: 8, alignItems: 'flex-end', marginBottom: 16 }}>
        <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
          <label htmlFor="api-key-label">Label</label>
          <input
            id="api-key-label"
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Production pipeline"
            maxLength={255}
            required
          />
        </div>
        <button type="submit" className="auth-submit" disabled={creating} style={{ whiteSpace: 'nowrap' }}>
          {creating ? 'Generating...' : 'Generate Key'}
        </button>
      </form>

      {/* Generated key modal */}
      {generatedKey && (
        <div className="modal-overlay" onClick={() => setGeneratedKey(null)}>
          <div className="modal-content login-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>API Key Generated</h3>
              <button className="modal-close" onClick={() => setGeneratedKey(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <p style={{ color: '#d97706', fontWeight: 'bold', marginBottom: 8 }}>
                Copy this key now. It will not be shown again.
              </p>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <code style={{
                  flex: 1, padding: '8px 12px', background: '#f1f5f9',
                  borderRadius: 4, wordBreak: 'break-all', fontSize: 13
                }}>
                  {generatedKey.key}
                </code>
                <button onClick={handleCopy} className="auth-submit" style={{ whiteSpace: 'nowrap' }}>
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Key list */}
      {keys.length === 0 ? (
        <p style={{ color: '#6b7280' }}>No API keys generated yet.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Label</th>
              <th>Key Prefix</th>
              <th>Created By</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id}>
                <td>{k.label}</td>
                <td><code>{k.key_prefix}...</code></td>
                <td>{k.created_by_email || '-'}</td>
                <td>{new Date(k.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    className="admin-btn-danger"
                    onClick={() => setDeleteTarget({ id: k.id, label: k.label })}
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {deleteTarget && (
        <ConfirmModal
          title="Revoke API Key"
          message={`Are you sure you want to revoke the API key "${deleteTarget.label}"? Any applications using this key will lose access.`}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default ApiKeyManager;

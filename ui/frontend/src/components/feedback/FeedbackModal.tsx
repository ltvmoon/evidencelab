import React, { useState } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  url: string;
  screenshot: string | null;
  screenshotError: string | null;
}

// Server enforces a 200 KB cap on the JSONB `context` column. Reject early
// so the user gets clear feedback instead of a 422 from the server.
const MAX_SCREENSHOT_BYTES = 180_000;

const FeedbackModal: React.FC<FeedbackModalProps> = ({
  isOpen,
  onClose,
  url,
  screenshot,
  screenshotError,
}) => {
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const screenshotTooLarge =
    screenshot !== null && screenshot.length > MAX_SCREENSHOT_BYTES;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comment.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const context = screenshot && !screenshotTooLarge ? { screenshot } : null;
      await axios.post(`${API_BASE_URL}/ratings/`, {
        rating_type: 'page_feedback',
        reference_id: url.slice(0, 255),
        score: 3,
        comment: comment.trim(),
        url,
        context,
      });
      setSubmitted(true);
    } catch (err: unknown) {
      const responseData = (err as { response?: { data?: unknown } } | null)?.response?.data;
      setSubmitError(responseData ? JSON.stringify(responseData) : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setComment('');
    setSubmitError(null);
    setSubmitted(false);
    onClose();
  };

  return (
    <div
      className="rating-modal-overlay"
      onClick={handleClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
    >
      <div
        className="modal-panel feedback-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 520, width: '92%', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="modal-header">
          <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>Send feedback</h2>
          <div className="modal-header-actions">
            <button onClick={handleClose} className="modal-close" aria-label="Close">×</button>
          </div>
        </div>

        {submitted ? (
          <div className="modal-body" style={{ padding: '24px 20px', textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>Thanks — your feedback was submitted.</p>
            <button
              type="button"
              onClick={handleClose}
              style={{
                marginTop: 16,
                padding: '6px 14px',
                fontSize: '0.82rem',
                background: 'var(--brand-primary)',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="modal-body" style={{ padding: '16px 20px' }}>
              <div style={{ marginBottom: 12, fontSize: '0.78rem', color: 'var(--brand-text-secondary)' }}>
                <strong>Page:</strong>{' '}
                <span style={{ wordBreak: 'break-all' }}>{url}</span>
              </div>

              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--brand-text-secondary)', marginBottom: 4 }}>
                  Screenshot
                </div>
                {screenshot && !screenshotTooLarge && (
                  <img
                    src={screenshot}
                    alt="Screenshot of current page"
                    style={{
                      width: '100%',
                      border: '1px solid var(--brand-border)',
                      borderRadius: 6,
                      maxHeight: 220,
                      objectFit: 'contain',
                      background: '#f7f7f7',
                    }}
                  />
                )}
                {screenshotError && (
                  <p style={{ margin: 0, color: 'var(--brand-error)', fontSize: '0.78rem' }}>
                    Could not capture screenshot: {screenshotError}. Feedback will be submitted without it.
                  </p>
                )}
                {screenshotTooLarge && (
                  <p style={{ margin: 0, color: 'var(--brand-error)', fontSize: '0.78rem' }}>
                    Screenshot too large to attach; feedback will be submitted without it.
                  </p>
                )}
              </div>

              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Tell us what went well or what needs improvement…"
                rows={4}
                maxLength={2000}
                required
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  border: '1px solid var(--brand-border)',
                  borderRadius: 6,
                  resize: 'vertical',
                  fontSize: '0.85rem',
                  fontFamily: 'inherit',
                }}
              />

              {submitError && (
                <p style={{ margin: '8px 0 0', color: 'var(--brand-error)', fontSize: '0.78rem' }}>
                  {submitError}
                </p>
              )}
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                padding: '12px 20px',
                borderTop: '1px solid var(--brand-border-light)',
                gap: 8,
              }}
            >
              <button
                type="button"
                onClick={handleClose}
                disabled={submitting}
                style={{
                  padding: '6px 14px',
                  fontSize: '0.82rem',
                  background: 'transparent',
                  color: 'var(--brand-text-secondary)',
                  border: '1px solid var(--brand-border)',
                  borderRadius: 6,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !comment.trim()}
                style={{
                  padding: '6px 14px',
                  fontSize: '0.82rem',
                  background:
                    submitting || !comment.trim()
                      ? 'var(--brand-border)'
                      : 'var(--brand-primary)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  cursor: submitting || !comment.trim() ? 'not-allowed' : 'pointer',
                }}
              >
                {submitting ? 'Submitting…' : 'Submit'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default FeedbackModal;

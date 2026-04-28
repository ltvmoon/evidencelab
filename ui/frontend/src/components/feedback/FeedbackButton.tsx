import React, { useState } from 'react';
import html2canvas from 'html2canvas';
import FeedbackModal from './FeedbackModal';

const FeedbackButton: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [screenshotError, setScreenshotError] = useState<string | null>(null);
  const [url, setUrl] = useState('');

  const handleOpen = async () => {
    setCapturing(true);
    setScreenshot(null);
    setScreenshotError(null);
    setUrl(window.location.href);

    try {
      const canvas = await html2canvas(document.documentElement, {
        scale: 0.5,
        logging: false,
        useCORS: true,
        backgroundColor: '#ffffff',
      });
      setScreenshot(canvas.toDataURL('image/jpeg', 0.6));
    } catch (err: unknown) {
      setScreenshotError(err instanceof Error ? err.message : 'unknown error');
    } finally {
      setCapturing(false);
      setOpen(true);
    }
  };

  const handleClose = () => {
    setOpen(false);
    setScreenshot(null);
    setScreenshotError(null);
  };

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        disabled={capturing}
        aria-label="Send feedback"
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 9000,
          padding: '10px 16px',
          fontSize: '0.85rem',
          fontWeight: 600,
          background: 'var(--brand-primary, #2c5cdc)',
          color: '#fff',
          border: 'none',
          borderRadius: 999,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          cursor: capturing ? 'wait' : 'pointer',
          opacity: capturing ? 0.7 : 1,
        }}
      >
        {capturing ? 'Capturing…' : 'Feedback'}
      </button>
      <FeedbackModal
        isOpen={open}
        onClose={handleClose}
        url={url}
        screenshot={screenshot}
        screenshotError={screenshotError}
      />
    </>
  );
};

export default FeedbackButton;

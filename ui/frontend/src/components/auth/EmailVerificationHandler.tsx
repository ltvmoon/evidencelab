import React, { useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config';

/**
 * Handles the `?verify=TOKEN` URL parameter on page load.
 *
 * When a user clicks the verification link in their email they land on
 * the app with `?verify=<jwt>`.  This component detects the token,
 * POSTs it to the backend verify endpoint, displays a result banner,
 * and cleans the URL.
 */
const EmailVerificationHandler: React.FC = () => {
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('verify');
    if (!token) return;

    // Clean the URL immediately so a page refresh won't re-verify
    params.delete('verify');
    const clean = params.toString();
    const newUrl = window.location.pathname + (clean ? `?${clean}` : '');
    window.history.replaceState({}, '', newUrl);

    const verify = async () => {
      try {
        await axios.post(`${API_BASE_URL}/auth/verify`, { token });
        setMessage(
          'Your email has been verified! You can now sign in.'
        );
        setIsError(false);
      } catch (err: any) {
        const detail = err.response?.data?.detail;
        if (
          typeof detail === 'string' &&
          detail.toLowerCase().includes('already verified')
        ) {
          setMessage('This email is already verified. You can sign in.');
          setIsError(false);
        } else {
          setMessage(
            typeof detail === 'string'
              ? detail
              : 'Email verification failed. The link may have expired.'
          );
          setIsError(true);
        }
      }
    };

    verify();
  }, []);

  if (!message) return null;

  return (
    <div
      className={isError ? 'auth-error' : 'auth-success'}
      style={{
        position: 'fixed',
        top: '1rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10000,
        maxWidth: '480px',
        width: '90%',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      }}
    >
      <span>{message}</span>
      <button
        className="auth-error-dismiss"
        onClick={() => setMessage(null)}
        aria-label="Dismiss"
        style={{ marginLeft: '0.5rem' }}
      >
        &times;
      </button>
    </div>
  );
};

export default EmailVerificationHandler;

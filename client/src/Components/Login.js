import React, { useEffect, useRef, useState } from 'react';
import ccsLogo from '../assets/ccs_logo.png';
import SERVER_URL, { GOOGLE_CLIENT_ID } from '../config.js';
import '../Login.css';

const GSI_SRC = 'https://accounts.google.com/gsi/client';

// Loads the Google Identity Services script once and resolves with window.google
const loadGoogleIdentity = () => new Promise((resolve, reject) => {
  if (window.google?.accounts?.id) return resolve(window.google);
  let script = document.querySelector(`script[src="${GSI_SRC}"]`);
  if (!script) {
    script = document.createElement('script');
    script.src = GSI_SRC;
    script.async = true;
    document.head.appendChild(script);
  }
  script.addEventListener('load', () => resolve(window.google));
  script.addEventListener('error', () => reject(new Error('Failed to load Google Sign-In')));
});

const Login = ({ onLogin }) => {
  const buttonRef = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleCredential = async ({ credential }) => {
      setError(null);
      try {
        const response = await fetch(`${SERVER_URL}/api/auth/google/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credential }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Error: ${response.status}`);
        localStorage.setItem('token', data.token);
        onLogin(data.user);
      } catch (err) {
        setError(err.message);
      }
    };

    if (!GOOGLE_CLIENT_ID) {
      setError('REACT_APP_GOOGLE_CLIENT_ID is not set');
      return;
    }
    loadGoogleIdentity()
      .then(google => {
        google.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: handleCredential });
        google.accounts.id.renderButton(buttonRef.current, { theme: 'outline', size: 'large', text: 'signin_with' });
      })
      .catch(err => setError(err.message));
  }, [onLogin]);

  return (
    <div className="login-outer-container">
      <div className="login-container">
        <div className="logo-section">
          <img src={ccsLogo} alt="CCS Logo" className="ccs-logo" />
        </div>
        <div className="form-section">
          <h2>CCS Coding Community</h2>
          <div ref={buttonRef} />
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </div>
  );
};

export default Login;

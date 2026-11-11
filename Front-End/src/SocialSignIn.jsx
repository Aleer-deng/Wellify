import React, { useEffect, useState } from 'react';
import { api, signInWithProvider } from './api';
import './social-sign-in.css';

const providers = [{ id: 'google', name: 'Google' }, { id: 'apple', name: 'Apple' }, { id: 'microsoft', name: 'Microsoft' }];
const errors = {
  inactive: 'This account is unavailable. Contact Wellify support.',
  email_required: 'Your provider did not share an email address. Try another account or use email sign-in.',
  existing_account: 'An account with this email already exists. Please sign in with your original method.',
  provider_failed: 'Sign-in was cancelled or could not be completed. Please try again.',
};

function ProviderIcon({ id }) {
  if (id === 'google') return <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-1.99 3.02v2.51h3.23c1.89-1.74 2.98-4.31 2.98-7.36Z"/><path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.41l-3.23-2.51c-.9.6-2.04.97-3.39.97-2.61 0-4.83-1.77-5.62-4.15H3.04v2.59A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.38 13.9a6 6 0 0 1 0-3.8V7.51H3.04a10 10 0 0 0 0 8.98Z"/><path fill="#EA4335" d="M12 5.95c1.47 0 2.79.51 3.83 1.52l2.87-2.87A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.96 5.51l3.34 2.59A5.97 5.97 0 0 1 12 5.95Z"/></svg>;
  if (id === 'microsoft') return <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#f25022" d="M1 1h10v10H1z"/><path fill="#7fba00" d="M13 1h10v10H13z"/><path fill="#00a4ef" d="M1 13h10v10H1z"/><path fill="#ffb900" d="M13 13h10v10H13z"/></svg>;
  return <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.05 12.54c.03 3.08 2.7 4.1 2.73 4.12-.02.07-.43 1.47-1.41 2.92-.85 1.25-1.74 2.49-3.13 2.52-1.37.03-1.81-.81-3.38-.81-1.56 0-2.05.79-3.35.84-1.35.05-2.38-1.35-3.24-2.6-1.76-2.55-3.1-7.2-1.29-10.34a5.02 5.02 0 0 1 4.24-2.57c1.32-.03 2.57.9 3.38.9.81 0 2.33-1.12 3.93-.95.67.03 2.55.27 3.76 2.04-.1.06-2.25 1.31-2.24 3.93ZM14.47 4.88c.71-.86 1.19-2.05 1.06-3.24-1.02.04-2.26.68-2.99 1.54-.66.76-1.23 1.97-1.08 3.14 1.13.09 2.29-.57 3.01-1.44Z"/></svg>;
}

export default function SocialSignIn({ disabled }) {
  const [available, setAvailable] = useState(null);
  const [pending, setPending] = useState('');
  const [message, setMessage] = useState(() => errors[new URLSearchParams(window.location.search).get('auth_error')] || '');
  useEffect(() => {
    let active = true;
    api('/auth/providers/').then(data => { if (active) setAvailable(data.providers); })
      .catch(() => { if (active) { setAvailable([]); setMessage('Account sign-in options are unavailable. You can still use your email and password.'); } });
    const url = new URL(window.location.href);
    if (url.searchParams.has('auth_error')) { url.searchParams.delete('auth_error'); window.history.replaceState(null, '', url); }
    return () => { active = false; };
  }, []);
  async function signIn(provider) {
    if (!available?.find(item => item.id === provider.id)?.enabled) {
      setMessage(`${provider.name} sign-in is not available yet. Please use your email and password for now.`);
      return;
    }
    setMessage(''); setPending(provider.id);
    try { await signInWithProvider(provider.id); }
    catch (error) { setMessage(error.message); setPending(''); }
  }
  return <div className="social-sign-in">
    <div className="social-buttons" aria-label="Other ways to sign in">
      {providers.map(provider => <button type="button" className={`social-button social-${provider.id}`} key={provider.id}
        disabled={disabled || !!pending || available === null} onClick={() => signIn(provider)}>
        <ProviderIcon id={provider.id}/><span>{pending === provider.id ? 'Connecting…' : `Continue with ${provider.name}`}</span>
      </button>)}
    </div>
    {message && <p className="social-message" role="alert">{message}</p>}
    <div className="auth-divider"><span>or sign in with email</span></div>
  </div>;
}

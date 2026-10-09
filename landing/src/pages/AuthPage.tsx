import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Logo } from '../components/Logo';
import { AlertCircle, CheckCircle2, ArrowLeft } from 'lucide-react';

interface AuthPageProps {
  onBackToHome?: () => void;
  onSuccess?: () => void;
  returnUrl?: string;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onBackToHome, onSuccess, returnUrl }) => {
  const {
    user,
    signIn,
    signUp,
    signInWithGoogle,
    sendReset,
    isConfigured,
    configError,
  } = useAuth();

  const [tab, setTab] = useState<'signin' | 'signup' | 'forgot'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // If already signed in
  if (user) {
    if (onSuccess) {
      onSuccess();
    } else if (returnUrl) {
      window.location.href = returnUrl;
    }
  }

  const validate = () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Enter a valid email address.');
      return false;
    }
    if (tab !== 'forgot' && (!password || password.length < 6)) {
      setError('Use at least 6 characters for your password.');
      return false;
    }
    return true;
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);

    if (!validate()) return;
    setSubmitting(true);

    if (tab === 'signin') {
      const res = await signIn(email, password);
      setSubmitting(false);
      if (!res.success) {
        setError(res.error || 'Sign-in failed.');
      } else {
        if (onSuccess) onSuccess();
        else if (returnUrl) window.location.href = returnUrl;
      }
    } else if (tab === 'signup') {
      const res = await signUp(email, password);
      setSubmitting(false);
      if (!res.success) {
        setError(res.error || 'Sign-up failed.');
      } else {
        setNotice('Account created! Check your inbox to verify your email.');
      }
    } else if (tab === 'forgot') {
      const res = await sendReset(email);
      setSubmitting(false);
      if (!res.success) {
        setError(res.error || 'Password reset failed.');
      } else {
        setNotice('If there is an account with that email, a password reset link has been sent.');
      }
    }
  };

  const handleGoogleSubmit = async () => {
    setError(null);
    setNotice(null);
    setSubmitting(true);
    const res = await signInWithGoogle();
    setSubmitting(false);
    if (!res.success) {
      setError(res.error || 'Google sign-in failed.');
    } else {
      if (onSuccess) onSuccess();
      else if (returnUrl) window.location.href = returnUrl;
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-page px-6 py-12 text-ink selection:bg-brand-soft selection:text-brand-ink">
      <div className="w-full max-w-[420px]">
        {/* Header with back button */}
        <div className="mb-8 flex items-center justify-between">
          <button
            type="button"
            onClick={onBackToHome || (() => (window.location.href = '/'))}
            className="flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-ink"
          >
            <ArrowLeft size={16} />
            Back
          </button>
          <Logo size={28} showWordmark={true} />
        </div>

        {/* Configuration Setup Warning if env vars not provided */}
        {!isConfigured && (
          <div className="mb-6 rounded-2xl border border-warn/30 bg-warn-soft p-4 text-xs leading-relaxed text-warn">
            <div className="flex items-start gap-2.5">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Firebase environment setup required</p>
                <p className="mt-1 text-muted">
                  {configError || 'Please configure VITE_FIREBASE_* in your environment.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Notice Message */}
        {notice && (
          <div className="mb-5 flex items-start gap-3 rounded-2xl bg-ok-soft p-4 text-sm text-ok">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
            <span>{notice}</span>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-5 flex items-start gap-3 rounded-2xl bg-bad-soft p-4 text-sm text-bad">
            <AlertCircle size={18} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Card Container */}
        <div className="rounded-[32px] bg-card p-8 shadow-soft-lg border border-line">
          {/* Tabs for Sign in / Create account */}
          {tab !== 'forgot' && (
            <div className="mb-6 flex rounded-full bg-surface p-1">
              <button
                type="button"
                onClick={() => {
                  setTab('signin');
                  setError(null);
                  setNotice(null);
                }}
                className={`flex-1 rounded-full py-2 text-sm font-semibold transition-all ${
                  tab === 'signin'
                    ? 'bg-card text-ink shadow-sm'
                    : 'text-muted hover:text-ink'
                }`}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => {
                  setTab('signup');
                  setError(null);
                  setNotice(null);
                }}
                className={`flex-1 rounded-full py-2 text-sm font-semibold transition-all ${
                  tab === 'signup'
                    ? 'bg-card text-ink shadow-sm'
                    : 'text-muted hover:text-ink'
                }`}
              >
                Create account
              </button>
            </div>
          )}

          {tab === 'forgot' && (
            <div className="mb-6">
              <h2 className="text-xl font-bold tracking-tight text-ink">Reset password</h2>
              <p className="mt-1 text-xs text-muted">
                Enter your email address to receive password reset instructions.
              </p>
            </div>
          )}

          {/* Google Sign-in Button */}
          {tab !== 'forgot' && (
            <>
              <button
                type="button"
                onClick={handleGoogleSubmit}
                disabled={submitting}
                className="flex h-12 w-full items-center justify-center gap-3 rounded-full border border-hair bg-card text-sm font-medium text-ink transition-all hover:bg-surface disabled:opacity-50"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                Continue with Google
              </button>

              <div className="relative my-6 text-center text-xs text-muted">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-line" />
                </div>
                <span className="relative bg-card px-3">or with email</span>
              </div>
            </>
          )}

          {/* Form */}
          <form onSubmit={handleEmailSubmit} className="space-y-4">
            <div>
              <label htmlFor="auth-email" className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                Email
              </label>
              <div className="relative">
                <input
                  id="auth-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="owner@company.com"
                  required
                  className="h-11 w-full rounded-xl border border-hair bg-surface px-3.5 text-sm text-ink outline-none transition-colors focus:border-brand focus:bg-card"
                />
              </div>
            </div>

            {tab !== 'forgot' && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="auth-pass" className="block text-xs font-semibold text-muted uppercase tracking-wider">
                    Password
                  </label>
                  {tab === 'signin' && (
                    <button
                      type="button"
                      onClick={() => {
                        setTab('forgot');
                        setError(null);
                        setNotice(null);
                      }}
                      className="text-xs text-brand hover:underline"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <input
                  id="auth-pass"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="h-11 w-full rounded-xl border border-hair bg-surface px-3.5 text-sm text-ink outline-none transition-colors focus:border-brand focus:bg-card"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 flex h-11 w-full items-center justify-center rounded-full bg-brand text-sm font-semibold text-white transition-all hover:bg-brand-hover disabled:opacity-50 shadow-sm"
            >
              {submitting
                ? 'Processing...'
                : tab === 'signin'
                ? 'Sign in to AgentGuard'
                : tab === 'signup'
                ? 'Create Account'
                : 'Send Reset Link'}
            </button>

            {tab === 'forgot' && (
              <button
                type="button"
                onClick={() => {
                  setTab('signin');
                  setError(null);
                  setNotice(null);
                }}
                className="w-full text-center text-xs font-medium text-muted hover:text-ink pt-2"
              >
                Back to sign in
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
};

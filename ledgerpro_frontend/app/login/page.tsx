'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useAuth } from '../auth-context';
import { useTheme } from '../providers';
import { useRouter, useSearchParams } from 'next/navigation';
import { Moon, Sun } from 'lucide-react';
import SaasFooter from '../components/saas-footer';
import LedgerProLogo from '../components/ledgerpro-logo';

function LoginContent() {
  const { initiateGoogleLogin, loginWithEmail } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();

  // Handle errors passed back from Google OAuth redirect
  useEffect(() => {
    const err = searchParams.get('error');
    if (err === 'oauth_failed') setError('Google sign-in failed. Please try again.');
    if (err === 'email_not_verified') setError('Your Google email is not verified.');
  }, [searchParams]);

  const handleGoogleLogin = () => {
    setGoogleLoading(true);
    setError('');
    initiateGoogleLogin();
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await loginWithEmail(email.trim());
      if (result.pending_2fa && result.pending_token) {
        sessionStorage.setItem('pending_2fa_token', result.pending_token);
        sessionStorage.setItem('pending_email', result.email || email.trim());
        router.push('/verify-otp');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your email and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary text-text-primary transition-colors duration-200">
      {/* Theme toggle */}
      <div className="flex justify-end px-6 pt-6">
        <button
          onClick={toggleTheme}
          className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
          aria-label="Toggle theme"
        >
          {mounted && theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
      </div>

      {/* Card */}
      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm border border-border-subtle rounded-xl bg-bg-secondary p-8 space-y-6">
          {/* Logo + heading */}
          <div className="text-center space-y-2">
            <LedgerProLogo size="lg" href="/" className="justify-center" />
            <h1 className="text-xl font-semibold text-text-primary mt-3">Sign in to LedgerPro</h1>
            <p className="text-sm text-text-secondary">Your secure accountant workspace</p>
          </div>

          {/* Error message */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-500 text-sm rounded-lg">
              {error}
            </div>
          )}

          {/* Google Sign-In */}
          <button
            id="google-login-btn"
            onClick={handleGoogleLogin}
            disabled={googleLoading || loading}
            className="w-full py-3 border border-border-subtle bg-bg-primary hover:bg-bg-secondary rounded-lg flex items-center justify-center gap-3 transition-all text-sm font-medium text-text-primary disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {googleLoading ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-text-secondary border-t-transparent rounded-full animate-spin" />
                Connecting to Google…
              </span>
            ) : (
              <>
                <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
                Continue with Google
              </>
            )}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 border-t border-border-subtle" />
            <span className="text-xs text-text-secondary">or sign in with email</span>
            <div className="flex-1 border-t border-border-subtle" />
          </div>

          {/* Email login form */}
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="block text-sm text-text-secondary mb-1">
                Email address
              </label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yourfirm.com"
                required
                className="w-full px-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all"
              />
            </div>
            <button
              id="email-login-btn"
              type="submit"
              disabled={loading || googleLoading}
              className="w-full py-2.5 bg-accent text-accent-foreground rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-accent-foreground/50 border-t-transparent rounded-full animate-spin" />
                  Sending OTP…
                </span>
              ) : (
                'Send OTP Code'
              )}
            </button>
          </form>

          {/* Footer note */}
          <p className="text-center text-xs text-text-secondary">
            A 6-digit verification code will be sent to your email.
          </p>

          {/* Register link */}
          <p className="text-center text-sm text-text-secondary pt-1">
            Don&apos;t have an account?{' '}
            <button
              onClick={() => router.push('/register')}
              className="text-text-primary font-medium hover:underline transition-colors"
              type="button"
            >
              Register here
            </button>
          </p>
        </div>
      </div>

      <SaasFooter variant="minimal" />
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}

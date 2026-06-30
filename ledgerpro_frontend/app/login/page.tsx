'use client';

import React, { useState } from 'react';
import { useAuth } from '../auth-context';
import { useTheme } from '../providers';
import { useRouter } from 'next/navigation';
import { Loader2, Moon, Sun } from 'lucide-react';
import SaasFooter from '../components/saas-footer';

export default function LoginPage() {
  const { loginWithGoogleToken } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleMockGoogleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Please enter a valid email address');
      return;
    }
    setLoading(true);
    setError('');

    try {
      // Simulate Google OAuth token response
      const mockGoogleToken = `mock_dev_token_${email}`;
      const result = await loginWithGoogleToken(mockGoogleToken);
      if (result.pending_2fa && result.pending_token) {
        // Save pending token and email in sessionStorage to pass to verify-otp page
        sessionStorage.setItem('pending_2fa_token', result.pending_token);
        sessionStorage.setItem('pending_email', result.email || email);
        router.push('/verify-otp');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary text-text-primary font-sans transition-colors duration-200">
      <div className="flex justify-end px-6 pt-6">
        <button
          onClick={toggleTheme}
          className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
          aria-label="Toggle theme"
        >
          {mounted && theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
      <div className="w-full max-w-md border border-border-subtle rounded-lg bg-bg-secondary p-8 space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold tracking-tight">LedgerPro</h2>
          <p className="text-sm text-text-secondary mt-2">Sign in to your accountant workspace</p>
        </div>

        {error && (
          <div className="p-3 bg-bg-primary border border-red-500/30 text-red-500 text-xs font-mono rounded break-words">
            {error}
          </div>
        )}

        {/* Continue with Google button */}
        <div className="space-y-4">
          <button
            onClick={() => {
              const inputEmail = prompt("Please enter your email to simulate Google Sign-In:", "accountant@ledgerpro.com");
              if (inputEmail) {
                setEmail(inputEmail);
                const mockToken = `mock_dev_token_${inputEmail}`;
                setLoading(true);
                loginWithGoogleToken(mockToken)
                  .then((res) => {
                    if (res.pending_2fa && res.pending_token) {
                      sessionStorage.setItem('pending_2fa_token', res.pending_token);
                      sessionStorage.setItem('pending_email', res.email || inputEmail);
                      router.push('/verify-otp');
                    }
                  })
                  .catch((err) => setError(err.message))
                  .finally(() => setLoading(false));
              }
            }}
            disabled={loading}
            className="w-full py-3 border border-border-subtle bg-bg-primary hover:bg-bg-secondary rounded flex items-center justify-center gap-3 transition-all active:scale-98 text-sm font-semibold"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            {loading ? (
              <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Connecting…</span>
            ) : 'Continue with Google'}
          </button>
        </div>

        <div className="relative flex py-2 items-center">
          <div className="flex-grow border-t border-border-subtle"></div>
          <span className="flex-shrink mx-4 text-xs font-mono text-text-secondary uppercase">Developer Login</span>
          <div className="flex-grow border-t border-border-subtle"></div>
        </div>

        {/* Developer simulated login form */}
        <form onSubmit={handleMockGoogleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-text-secondary mb-1">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. accountant@ledgerpro.com"
              required
              className="w-full px-3 py-2 bg-bg-primary border border-border-subtle rounded text-sm focus:outline-none focus:border-accent text-text-primary"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-accent text-accent-foreground rounded text-sm font-semibold hover:opacity-90 transition-opacity active:scale-98"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Generating OTP…</span>
            ) : 'Send OTP Code'}
          </button>
        </form>
      </div>
      </div>
      <SaasFooter variant="minimal" />
    </div>
  );
}

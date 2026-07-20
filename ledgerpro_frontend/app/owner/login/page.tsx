'use client';

import React, { useState } from 'react';
import { useAuth } from '../../auth-context';
import { useTheme } from '../../providers';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Moon, Sun, Shield } from 'lucide-react';
import SaasFooter from '../../components/saas-footer';
import LedgerProLogo from '../../components/ledgerpro-logo';

export default function OwnerLoginPage() {
  const { loginAsOwner } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleOwnerLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter the owner email used when your firm was registered.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await loginAsOwner(email.trim());
      if (result.pending_2fa && result.pending_token) {
        sessionStorage.setItem('pending_2fa_token', result.pending_token);
        sessionStorage.setItem('pending_email', result.email || email.trim());
        sessionStorage.setItem('auth_flow', 'owner');
        router.push('/verify-otp');
      }
    } catch (err: any) {
      setError(err.message || 'Owner login failed. Check that this email matches your firm owner email.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary text-text-primary transition-colors duration-200">
      <div className="flex justify-end px-6 pt-6">
        <button
          onClick={toggleTheme}
          className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
          aria-label="Toggle theme"
        >
          {mounted && theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm border border-border-subtle rounded-xl bg-bg-secondary p-8 space-y-6">
          <div className="text-center space-y-2">
            <LedgerProLogo size="lg" href="/" className="justify-center" />
            <div className="flex items-center justify-center gap-2 mt-3">
              <Shield className="w-5 h-5 text-text-secondary" />
              <h1 className="text-xl font-semibold text-text-primary">Owners Login</h1>
            </div>
            <p className="text-sm text-text-secondary">
              Read-only access to your firms. Use the same email your accountant registered as the owner email.
            </p>
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-500 text-sm rounded-lg">
              {error}
            </div>
          )}

          <form onSubmit={handleOwnerLogin} className="space-y-4">
            <div>
              <label htmlFor="owner-email" className="block text-sm text-text-secondary mb-1">
                Owner email
              </label>
              <input
                id="owner-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@yourbusiness.com"
                required
                className="w-full px-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
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

          <p className="text-center text-xs text-text-secondary">
            You can view activity, logins, and documents. Editing and uploads are disabled.
          </p>

          <p className="text-center text-sm text-text-secondary pt-1">
            Accountant?{' '}
            <Link href="/login" className="text-text-primary font-medium hover:underline transition-colors">
              Sign in here
            </Link>
          </p>
        </div>
      </div>

      <SaasFooter variant="minimal" />
    </div>
  );
}

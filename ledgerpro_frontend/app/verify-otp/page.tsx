'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../auth-context';
import { useTheme } from '../providers';
import { useRouter } from 'next/navigation';
import { Moon, Sun } from 'lucide-react';
import SaasFooter from '../components/saas-footer';
import LedgerProLogo from '../components/ledgerpro-logo';

function ThreeDotLoader({
  size = 'md',
  label,
}: {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}) {
  const px = size === 'sm' ? '6px' : size === 'md' ? '10px' : '12px';
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-4" role="status" aria-live="polite">
      <div className="inline-flex items-center justify-center gap-2 text-text-primary">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="rounded-full bg-current"
            style={{
              width: px,
              height: px,
              animation: 'dotBounce 1.2s ease-in-out infinite',
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>
      {label && (
        <p className="text-xs text-text-secondary font-mono animate-pulse">{label}</p>
      )}
    </div>
  );
}

export default function VerifyOtpPage() {
  const { verifyOTPCode, resendOTPCode } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  const [email, setEmail] = useState('');
  const [pendingToken, setPendingToken] = useState('');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusLabel, setStatusLabel] = useState('Verifying security code...');
  const [countdown, setCountdown] = useState(300);
  const verifyingRef = useRef(false);
  const router = useRouter();

  const inputRefs = [
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
  ];

  useEffect(() => {
    const savedToken = sessionStorage.getItem('pending_2fa_token');
    const savedEmail = sessionStorage.getItem('pending_email');
    if (!savedToken || !savedEmail) {
      const flow = sessionStorage.getItem('auth_flow');
      router.push(flow === 'owner' ? '/owner/login' : '/login');
    } else {
      setPendingToken(savedToken);
      setEmail(savedEmail);
      setTimeout(() => inputRefs[0].current?.focus(), 100);
    }
  }, [router]);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => setCountdown((prev) => prev - 1), 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  // Auto-submit when all 6 digits are filled
  useEffect(() => {
    const fullCode = code.join('');
    if (fullCode.length === 6 && !code.includes('') && pendingToken && !verifyingRef.current) {
      handleVerify(fullCode);
    }
  }, [code, pendingToken]);

  const handleVerify = async (verificationCode: string) => {
    if (verifyingRef.current) return;
    verifyingRef.current = true;
    setLoading(true);
    setStatusLabel('Verifying security code...');
    setError('');
    setSuccessMsg('');
    try {
      await verifyOTPCode(pendingToken, verificationCode);
      // Keep loader visible while navigation to dashboard completes
      setStatusLabel('Signing you in...');
    } catch (err: any) {
      verifyingRef.current = false;
      setLoading(false);
      setError(err.message || 'Verification failed. Please try again.');
      setCode(['', '', '', '', '', '']);
      inputRefs[0].current?.focus();
    }
  };

  const handleInputChange = (index: number, value: string) => {
    if (loading) return;

    if (value.length > 1) {
      const digits = value.replace(/\D/g, '').slice(0, 6).split('');
      const newCode = ['', '', '', '', '', ''];
      digits.forEach((d, i) => {
        if (i < 6) newCode[i] = d;
      });
      setCode(newCode);
      const nextEmpty = newCode.findIndex((d) => !d);
      const focusIndex = nextEmpty === -1 ? 5 : nextEmpty;
      inputRefs[focusIndex].current?.focus();
      return;
    }

    if (value && !/^\d$/.test(value)) return;
    const newCode = [...code];
    newCode[index] = value;
    setCode(newCode);
    if (value && index < 5) {
      inputRefs[index + 1].current?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (loading) return;
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs[index - 1].current?.focus();
      const newCode = [...code];
      newCode[index - 1] = '';
      setCode(newCode);
    }
  };

  const handleResend = async () => {
    if (countdown > 0 || !pendingToken || loading) return;
    setLoading(true);
    setStatusLabel('Sending a new code...');
    setError('');
    setSuccessMsg('');
    try {
      const newToken = await resendOTPCode(pendingToken);
      sessionStorage.setItem('pending_2fa_token', newToken);
      setPendingToken(newToken);
      setCountdown(300);
      setCode(['', '', '', '', '', '']);
      setSuccessMsg('A new verification code has been sent to your email.');
      inputRefs[0].current?.focus();
    } catch (err: any) {
      setError(err.message || 'Failed to resend code.');
    } finally {
      setLoading(false);
      verifyingRef.current = false;
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const backHref = typeof window !== 'undefined' && sessionStorage.getItem('auth_flow') === 'owner'
    ? '/owner/login'
    : '/login';

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary text-text-primary transition-colors duration-200">
      <div className="flex justify-end px-6 pt-6">
        <button
          onClick={toggleTheme}
          className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
          aria-label="Toggle theme"
          disabled={loading}
        >
          {mounted && theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm border border-border-subtle rounded-xl bg-bg-secondary p-8 space-y-6 relative">
          <div className="text-center space-y-2">
            <LedgerProLogo size="lg" href="/" className="justify-center" />
            <h1 className="text-xl font-semibold text-text-primary mt-3">Check your email</h1>
            <p className="text-sm text-text-secondary">
              We sent a 6-digit code to{' '}
              <span className="text-text-primary font-medium">{email}</span>
            </p>
          </div>

          {error && !loading && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-500 text-sm rounded-lg">
              {error}
            </div>
          )}

          {successMsg && !loading && (
            <div className="p-3 bg-green-500/10 border border-green-500/30 text-green-600 dark:text-green-400 text-sm rounded-lg">
              {successMsg}
            </div>
          )}

          {loading ? (
            <ThreeDotLoader size="md" label={statusLabel} />
          ) : (
            <div className="flex justify-center gap-2">
              {code.map((digit, index) => (
                <input
                  key={index}
                  ref={inputRefs[index]}
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={digit}
                  disabled={loading}
                  onChange={(e) => handleInputChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  className="w-11 text-center text-xl font-semibold bg-bg-primary border border-border-subtle rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary transition-all disabled:opacity-50"
                  style={{ height: '52px' }}
                />
              ))}
            </div>
          )}

          <div className="text-center space-y-3">
            <p className="text-sm text-text-secondary">
              {countdown > 0 ? (
                <>
                  Code expires in{' '}
                  <span className="text-text-primary font-medium">{formatTime(countdown)}</span>
                </>
              ) : (
                <span className="text-red-500 font-medium">Code expired</span>
              )}
            </p>
            <button
              onClick={handleResend}
              disabled={countdown > 0 || loading}
              className="text-sm text-text-secondary underline hover:text-text-primary transition-colors disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
            >
              {countdown > 0 ? `Resend code in ${formatTime(countdown)}` : 'Resend verification code'}
            </button>
          </div>

          <div className="text-center">
            <button
              onClick={() => router.push(backHref)}
              disabled={loading}
              className="text-sm text-text-secondary hover:text-text-primary hover:underline transition-colors disabled:opacity-40"
            >
              Back to login
            </button>
          </div>
        </div>
      </div>

      <SaasFooter variant="minimal" />

      <style>{`
        @keyframes dotBounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

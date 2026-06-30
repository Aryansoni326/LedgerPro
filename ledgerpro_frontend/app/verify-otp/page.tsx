'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../auth-context';
import { useTheme } from '../providers';
import { useRouter } from 'next/navigation';
import { Loader2, Moon, Sun } from 'lucide-react';
import SaasFooter from '../components/saas-footer';

export default function VerifyOtpPage() {
  const { verifyOTPCode, resendOTPCode } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  const [email, setEmail] = useState('');
  const [pendingToken, setPendingToken] = useState('');
  const [code, setCode] = useState(['', '', '', '']);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState(300); // 5 minutes (300s)
  const router = useRouter();

  const inputRefs = [
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null)
  ];

  // Retrieve pending token on mount
  useEffect(() => {
    const savedToken = sessionStorage.getItem('pending_2fa_token');
    const savedEmail = sessionStorage.getItem('pending_email');

    if (!savedToken || !savedEmail) {
      router.push('/login');
    } else {
      setPendingToken(savedToken);
      setEmail(savedEmail);
    }
  }, [router]);

  // Countdown timer effect
  useEffect(() => {
    if (countdown <= 0) return;

    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [countdown]);

  // Auto-trigger verification when code is fully entered
  useEffect(() => {
    const fullCode = code.join('');
    if (fullCode.length === 4 && pendingToken) {
      handleVerify(fullCode);
    }
  }, [code, pendingToken]);

  const handleVerify = async (verificationCode: string) => {
    setLoading(true);
    setError('');
    setSuccessMsg('');

    try {
      await verifyOTPCode(pendingToken, verificationCode);
      // AuthProvider redirects automatically on success, but fallback just in case
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Verification failed');
      // Clear inputs on failure to let user try again
      setCode(['', '', '', '']);
      inputRefs[0].current?.focus();
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (index: number, value: string) => {
    // Only allow numeric input
    if (value && !/^\d$/.test(value)) return;

    const newCode = [...code];
    newCode[index] = value;
    setCode(newCode);

    // Auto advance focus to the next box
    if (value && index < 3) {
      inputRefs[index + 1].current?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    // Handle backspace back-navigation
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs[index - 1].current?.focus();
      const newCode = [...code];
      newCode[index - 1] = '';
      setCode(newCode);
    }
  };

  const handleResend = async () => {
    if (countdown > 0 || !pendingToken) return;

    setLoading(true);
    setError('');
    setSuccessMsg('');

    try {
      const newToken = await resendOTPCode(pendingToken);
      sessionStorage.setItem('pending_2fa_token', newToken);
      setPendingToken(newToken);
      setCountdown(300); // Reset timer
      setCode(['', '', '', '']);
      setSuccessMsg('A new 4-digit verification code has been sent.');
      inputRefs[0].current?.focus();
    } catch (err: any) {
      setError(err.message || 'Failed to resend code');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
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
      <div className="w-full max-w-md border border-border-subtle rounded-lg bg-bg-secondary p-8 space-y-8 relative">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold tracking-tight">Security Check</h2>
          <p className="text-sm text-text-secondary mt-2">
            Enter the 4-digit code sent to <span className="font-mono text-text-primary font-semibold">{email}</span>
          </p>
        </div>

        {error && (
          <div className="p-3 bg-bg-primary border border-red-500/30 text-red-500 text-xs font-mono rounded break-words">
            {error}
          </div>
        )}

        {successMsg && (
          <div className="p-3 border border-border-subtle bg-bg-primary text-xs font-mono rounded text-center">
            {successMsg}
          </div>
        )}

        {/* 4-digit input fields */}
        {loading && (
          <div className="flex justify-center py-2">
            <Loader2 className="w-6 h-6 animate-spin text-text-primary" />
          </div>
        )}
        <div className={`flex justify-center gap-4 py-2 ${loading ? 'opacity-50 pointer-events-none' : ''}`}>
          {code.map((digit, index) => (
            <input
              key={index}
              ref={inputRefs[index]}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              disabled={loading}
              onChange={(e) => handleInputChange(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              className="w-14 h-16 text-center text-2xl font-bold bg-bg-primary border border-border-subtle rounded focus:outline-none focus:border-accent text-text-primary transition-all disabled:opacity-50"
            />
          ))}
        </div>

        <div className="text-center space-y-4">
          <div className="text-sm text-text-secondary font-mono">
            {countdown > 0 ? (
              <span>Code expires in: <span className="font-bold text-text-primary">{formatTime(countdown)}</span></span>
            ) : (
              <span className="text-red-500 font-bold">Code expired!</span>
            )}
          </div>

          <button
            onClick={handleResend}
            disabled={countdown > 0 || loading}
            className="text-xs font-mono underline hover:text-text-primary transition-colors disabled:opacity-40 disabled:no-underline"
          >
            {countdown > 0 ? `Resend code in ${formatTime(countdown)}` : 'Resend Verification Code'}
          </button>
        </div>

        <div className="text-center">
          <button
            onClick={() => router.push('/login')}
            className="text-xs font-mono text-text-secondary hover:underline"
          >
            Back to login
          </button>
        </div>
      </div>
      </div>
      <SaasFooter variant="minimal" />
    </div>
  );
}

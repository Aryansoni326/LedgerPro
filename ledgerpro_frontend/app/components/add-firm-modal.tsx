'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../auth-context';
import { X, UploadCloud, CheckCircle2, ShieldCheck, Mail, ArrowRight } from 'lucide-react';

interface AddFirmModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
  "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", 
  "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", 
  "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", 
  "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", 
  "Uttarakhand", "West Bengal"
];

export default function AddFirmModal({ isOpen, onClose }: AddFirmModalProps) {
  const { token, fetchFirms, setSelectedFirm, logout } = useAuth();
  const [step, setStep] = useState<1 | 2>(1);
  const [name, setName] = useState('');
  const [gstin, setGstin] = useState('');
  const [state, setState] = useState('');
  const [city, setCity] = useState('');
  const [ownerEmail, setOwnerEmail] = useState('');

  // OTP states
  const [firmId, setFirmId] = useState<number | null>(null);
  const [pendingToken, setPendingToken] = useState('');
  const [otpCode, setOtpCode] = useState(['', '', '', '', '', '']);
  const [countdown, setCountdown] = useState(300);
  
  // Feedback states
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const otpRefs = [
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null)
  ];

  useEffect(() => {
    if (!isOpen) {
      // Reset state on close
      setStep(1);
      setName('');
      setGstin('');
      setState('');
      setCity('');
      setOwnerEmail('');
      setFirmId(null);
      setPendingToken('');
      setOtpCode(['', '', '', '', '', '']);
      setError('');
      setFieldErrors({});
      setLoading(false);
    }
  }, [isOpen]);

  // OTP Countdown
  useEffect(() => {
    if (step !== 2 || countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [step, countdown]);

  // Auto trigger verification
  useEffect(() => {
    const codeStr = otpCode.join('');
    if (codeStr.length === 6 && firmId && pendingToken) {
      handleVerifyOtp(codeStr);
    }
  }, [otpCode, firmId, pendingToken]);

  const validateDetails = () => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Firm name is required.";
    if (!state) errs.state = "Please select a state.";
    if (!city.trim()) errs.city = "City is required.";
    if (!ownerEmail.trim()) {
      errs.ownerEmail = "Owner email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(ownerEmail)) {
      errs.ownerEmail = "Please enter a valid email address.";
    }

    if (gstin.trim()) {
      const gstinRegex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
      if (!gstinRegex.test(gstin.trim().toUpperCase())) {
        errs.gstin = "Invalid GSTIN format (15 characters standard regex, e.g. 27AAAAA1111A1Z1).";
      }
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleRegisterFirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateDetails()) return;
    
    setLoading(true);
    setError('');
    
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name,
          gstin: gstin.trim() || undefined,
          state,
          city,
          owner_email: ownerEmail
        })
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          logout();
          onClose();
          return;
        }
        if (data.errors) {
          setFieldErrors(data.errors);
        } else {
          setError(data.error || 'Failed to create firm.');
        }
        return;
      }

      setFirmId(data.id);
      setPendingToken(data.pending_token);
      setCountdown(300); // 5 min
      setStep(2);
    } catch (err: any) {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (codeStr: string) => {
    if (!firmId || !pendingToken) return;
    
    setLoading(true);
    setError('');

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${firmId}/verify-otp`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          pending_token: pendingToken,
          code: codeStr
        })
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          logout();
          onClose();
          return;
        }
        setError(data.error || 'Verification failed.');
        setOtpCode(['', '', '', '', '', '']);
        otpRefs[0].current?.focus();
        return;
      }

      // Success! Refresh list and select the new active firm
      await fetchFirms();
      setSelectedFirm({
        id: firmId,
        name,
        gstin,
        state,
        city,
        owner_email: ownerEmail,
        status: 'active',
        created_at: new Date().toISOString()
      });
      onClose();
    } catch (err) {
      setError('Connection failed. Please retry.');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (countdown > 0 || !firmId || !pendingToken) return;

    setLoading(true);
    setError('');

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${firmId}/resend-otp`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          pending_token: pendingToken
        })
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          logout();
          onClose();
          return;
        }
        setError(data.error || 'Failed to resend code.');
        return;
      }

      setPendingToken(data.pending_token);
      setCountdown(300);
      setOtpCode(['', '', '', '', '', '']);
      otpRefs[0].current?.focus();
      setError('');
    } catch (err) {
      setError('Failed to request new code.');
    } finally {
      setLoading(false);
    }
  };

  const handleOtpInputChange = (index: number, val: string) => {
    if (val && !/^\d$/.test(val)) return;

    const newCode = [...otpCode];
    newCode[index] = val;
    setOtpCode(newCode);

    if (val && index < 5) {
      otpRefs[index + 1].current?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otpCode[index] && index > 0) {
      otpRefs[index - 1].current?.focus();
      const newCode = [...otpCode];
      newCode[index - 1] = '';
      setOtpCode(newCode);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg border border-border-subtle rounded-lg bg-bg-secondary p-8 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
        
        {/* Close Button */}
        <button 
          onClick={onClose}
          disabled={loading}
          className="absolute top-4 right-4 p-1.5 border border-border-subtle rounded hover:bg-bg-primary transition-colors disabled:opacity-50"
        >
          <X className="w-4 h-4" />
        </button>

        {step === 1 ? (
          /* STEP 1: Details Form */
          <form onSubmit={handleRegisterFirm} className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Add Client Firm</h2>
              <p className="text-sm text-text-secondary mt-1">Register a new client ledger. Owner must verify email before uploading files.</p>
            </div>

            {error && (
              <div className="p-3 bg-bg-primary border border-red-500/30 text-red-500 text-xs font-mono rounded">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-text-secondary mb-1">Firm Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Apex Logistical Solutions"
                  className={`w-full px-3 py-2 bg-bg-primary border rounded text-sm focus:outline-none focus:border-accent text-text-primary ${fieldErrors.name ? 'border-red-500' : 'border-border-subtle'}`}
                />
                {fieldErrors.name && <span className="text-xs text-red-500 font-mono mt-0.5 block">{fieldErrors.name}</span>}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-mono text-text-secondary mb-1">GSTIN (Optional)</label>
                  <input
                    type="text"
                    value={gstin}
                    onChange={(e) => setGstin(e.target.value.toUpperCase())}
                    placeholder="e.g. 27AAAAA1111A1Z1"
                    maxLength={15}
                    className={`w-full px-3 py-2 bg-bg-primary border rounded text-sm focus:outline-none focus:border-accent text-text-primary ${fieldErrors.gstin ? 'border-red-500' : 'border-border-subtle'}`}
                  />
                  {fieldErrors.gstin && <span className="text-xs text-red-500 font-mono mt-0.5 block">{fieldErrors.gstin}</span>}
                </div>

                <div>
                  <label className="block text-xs font-mono text-text-secondary mb-1">State *</label>
                  <select
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className={`w-full px-3 py-2.5 bg-bg-primary border rounded text-sm focus:outline-none focus:border-accent text-text-primary ${fieldErrors.state ? 'border-red-500' : 'border-border-subtle'}`}
                  >
                    <option value="">Select State</option>
                    {INDIAN_STATES.map((st) => (
                      <option key={st} value={st}>{st}</option>
                    ))}
                  </select>
                  {fieldErrors.state && <span className="text-xs text-red-500 font-mono mt-0.5 block">{fieldErrors.state}</span>}
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-text-secondary mb-1">City *</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="e.g. Mumbai"
                  className={`w-full px-3 py-2 bg-bg-primary border rounded text-sm focus:outline-none focus:border-accent text-text-primary ${fieldErrors.city ? 'border-red-500' : 'border-border-subtle'}`}
                />
                {fieldErrors.city && <span className="text-xs text-red-500 font-mono mt-0.5 block">{fieldErrors.city}</span>}
              </div>

              <div>
                <label className="block text-xs font-mono text-text-secondary mb-1">Owner Email *</label>
                <input
                  type="email"
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  placeholder="e.g. owner@apexlogistics.com"
                  className={`w-full px-3 py-2 bg-bg-primary border rounded text-sm focus:outline-none focus:border-accent text-text-primary ${fieldErrors.ownerEmail ? 'border-red-500' : 'border-border-subtle'}`}
                />
                {fieldErrors.ownerEmail && <span className="text-xs text-red-500 font-mono mt-0.5 block">{fieldErrors.ownerEmail}</span>}
              </div>
            </div>

            <div className="pt-4 border-t border-border-subtle flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-4 py-2 border border-border-subtle rounded hover:bg-bg-primary text-sm font-semibold transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2 bg-accent text-accent-foreground rounded text-sm font-semibold hover:opacity-90 transition-opacity flex items-center gap-2 active:scale-95 disabled:opacity-50"
              >
                {loading ? 'Registering...' : 'Register Firm'} <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>
        ) : (
          /* STEP 2: OTP Verification */
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 border border-border-subtle bg-bg-primary rounded-full flex items-center justify-center mx-auto text-accent mb-2">
                <Mail className="w-6 h-6" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight">Verify Owner Email</h2>
              <p className="text-sm text-text-secondary max-w-sm mx-auto">
                A 6-digit verification code has been sent to <span className="font-mono text-text-primary font-semibold">{ownerEmail}</span>. Enter code below to activate firm.
              </p>
            </div>

            {error && (
              <div className="p-3 bg-bg-primary border border-red-500/30 text-red-500 text-xs font-mono rounded text-center">
                {error}
              </div>
            )}

            {/* Inputs */}
            <div className="flex justify-center gap-4 py-2">
              {otpCode.map((digit, idx) => (
                <input
                  key={idx}
                  ref={otpRefs[idx]}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  disabled={loading}
                  onChange={(e) => handleOtpInputChange(idx, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                  className="w-12 h-14 text-center text-xl font-bold bg-bg-primary border border-border-subtle rounded focus:outline-none focus:border-accent text-text-primary transition-all disabled:opacity-50"
                />
              ))}
            </div>

            <div className="text-center space-y-4 pt-2">
              <div className="text-xs font-mono text-text-secondary">
                {countdown > 0 ? (
                  <span>Verification session active: <span className="text-text-primary font-bold">{formatTime(countdown)}</span></span>
                ) : (
                  <span className="text-red-500 font-bold">Code expired!</span>
                )}
              </div>

              <button
                onClick={handleResendOtp}
                disabled={countdown > 0 || loading}
                className="text-xs font-mono underline hover:text-text-primary transition-colors disabled:opacity-40 disabled:no-underline"
              >
                {countdown > 0 ? `Resend code in ${formatTime(countdown)}` : 'Resend Verification Code'}
              </button>
            </div>

            <div className="pt-4 border-t border-border-subtle flex justify-between items-center text-xs">
              <button
                onClick={() => setStep(1)}
                disabled={loading}
                className="font-mono text-text-secondary hover:text-text-primary underline disabled:opacity-50"
              >
                Change details
              </button>
              <button
                onClick={onClose}
                disabled={loading}
                className="font-mono text-text-secondary hover:text-text-primary underline disabled:opacity-50"
              >
                Verify later
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

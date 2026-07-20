'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useAuth } from '../auth-context';
import { useTheme } from '../providers';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Moon,
  Sun,
  Calculator,
  Building2,
  ClipboardCheck,
  ArrowRight,
  ArrowLeft,
  User,
  Phone,
  MapPin,
  Briefcase,
  CreditCard,
  Mail,
} from 'lucide-react';
import SaasFooter from '../components/saas-footer';
import LedgerProLogo from '../components/ledgerpro-logo';

/* ────────────────────────────────────────────────────────────────────────── */
/* Role options                                                              */
/* ────────────────────────────────────────────────────────────────────────── */
const ROLES = [
  { value: 'accountant', label: 'Accountant', icon: Calculator, description: 'Managing client books' },
  { value: 'owner', label: 'Business Owner', icon: Building2, description: 'Running my own firm' },
  { value: 'auditor', label: 'Auditor', icon: ClipboardCheck, description: 'Compliance & auditing' },
] as const;

const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

/* ────────────────────────────────────────────────────────────────────────── */
/* Step indicator                                                            */
/* ────────────────────────────────────────────────────────────────────────── */
function StepIndicator({ current }: { current: 1 | 2 }) {
  return (
    <div className="flex items-center justify-center gap-3 mb-6">
      {[1, 2].map((step) => (
        <div key={step} className="flex items-center gap-2">
          <div
            className="register-step-dot"
            style={{
              width: step === current ? 28 : 8,
              background: step <= current
                ? 'var(--accent)'
                : 'var(--border-subtle)',
            }}
          />
          {step === 1 && (
            <div
              className="register-step-connector"
              style={{
                background: current >= 2 ? 'var(--accent)' : 'var(--border-subtle)',
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Google SVG (same as login page)                                           */
/* ────────────────────────────────────────────────────────────────────────── */
function GoogleIcon() {
  return (
    <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
    </svg>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Main registration content                                                 */
/* ────────────────────────────────────────────────────────────────────────── */
function RegisterContent() {
  const {
    registerWithGoogle,
    registerWithEmail,
    completeProfile,
  } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  const router = useRouter();
  const searchParams = useSearchParams();

  /* ── State ──────────────────────────────────────────────────────────── */
  const [step, setStep] = useState<1 | 2>(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  // Step 1 — email
  const [email, setEmail] = useState('');

  // Step 2 — profile
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [pan, setPan] = useState('');
  const [role, setRole] = useState('');
  const [location, setLocation] = useState('');
  const [registrationToken, setRegistrationToken] = useState('');

  /* ── Determine initial step from URL / sessionStorage ───────────── */
  useEffect(() => {
    const urlStep = searchParams.get('step');
    const urlError = searchParams.get('error');
    const savedToken = sessionStorage.getItem('registration_token');

    if (urlError === 'registration_failed') {
      setError('Google registration failed. Please try again.');
    }

    if (urlStep === 'profile' && savedToken) {
      // Coming back from Google OAuth or email flow
      setRegistrationToken(savedToken);
      setName(sessionStorage.getItem('registration_name') || '');
      setEmail(sessionStorage.getItem('registration_email') || '');
      setStep(2);
    }
  }, [searchParams]);

  /* ── Handlers ───────────────────────────────────────────────────── */
  const handleGoogleRegister = () => {
    setGoogleLoading(true);
    setError('');
    registerWithGoogle();
  };

  const handleEmailRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await registerWithEmail(email.trim());
      sessionStorage.setItem('registration_token', result.registration_token);
      sessionStorage.setItem('registration_email', result.email || email.trim());
      setRegistrationToken(result.registration_token);
      setStep(2);
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!name.trim()) { setError('Full name is required.'); return; }
    if (!phone.trim() || phone.replace(/\D/g, '').length < 10) {
      setError('Please enter a valid phone number (at least 10 digits).');
      return;
    }
    if (!role) { setError('Please select your role.'); return; }
    if (pan.trim() && !PAN_REGEX.test(pan.trim().toUpperCase())) {
      setError('Invalid PAN format. Expected: ABCDE1234F');
      return;
    }

    setLoading(true);
    try {
      const result = await completeProfile({
        registration_token: registrationToken,
        name: name.trim(),
        phone_number: phone.trim(),
        pan_number: pan.trim().toUpperCase() || undefined,
        role,
        location: location.trim() || undefined,
      });

      // Store pending_2fa_token and redirect to OTP verification
      sessionStorage.setItem('pending_2fa_token', result.pending_2fa_token);
      sessionStorage.setItem('pending_email', result.email || email);

      // Clean up registration session data
      sessionStorage.removeItem('registration_token');
      sessionStorage.removeItem('registration_email');
      sessionStorage.removeItem('registration_name');
      sessionStorage.removeItem('registration_avatar');

      router.push('/verify-otp');
    } catch (err: any) {
      setError(err.message || 'Profile completion failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  /* ── Render ─────────────────────────────────────────────────────── */
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
        <div className="w-full max-w-md border border-border-subtle rounded-xl bg-bg-secondary p-8 space-y-6 register-card">
          {/* Logo + heading */}
          <div className="text-center space-y-2">
            <LedgerProLogo size="lg" href="/" className="justify-center" />
            <h1 className="text-xl font-semibold text-text-primary mt-3">
              {step === 1 ? 'Create your LedgerPro account' : 'Complete your profile'}
            </h1>
            <p className="text-sm text-text-secondary">
              {step === 1
                ? 'Join thousands of accounting professionals'
                : 'Tell us a bit about yourself to get started'}
            </p>
          </div>

          {/* Step indicator */}
          <StepIndicator current={step} />

          {/* Error message */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-500 text-sm rounded-lg">
              {error}
            </div>
          )}

          {/* ──────────── Step 1: Auth method ──────────── */}
          {step === 1 && (
            <div className="space-y-5 register-step-animate">
              {/* Google */}
              <button
                onClick={handleGoogleRegister}
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
                    <GoogleIcon />
                    Continue with Google
                  </>
                )}
              </button>

              {/* Divider */}
              <div className="flex items-center gap-3">
                <div className="flex-1 border-t border-border-subtle" />
                <span className="text-xs text-text-secondary">or continue with email</span>
                <div className="flex-1 border-t border-border-subtle" />
              </div>

              {/* Email form */}
              <form onSubmit={handleEmailRegister} className="space-y-4">
                <div>
                  <label htmlFor="register-email" className="block text-sm text-text-secondary mb-1">
                    Email address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary/50" />
                    <input
                      id="register-email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@yourfirm.com"
                      required
                      className="w-full pl-10 pr-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={loading || googleLoading}
                  className="w-full py-2.5 bg-accent text-accent-foreground rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-accent-foreground/50 border-t-transparent rounded-full animate-spin" />
                      Creating account…
                    </span>
                  ) : (
                    <>
                      Continue
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>

              {/* Login link */}
              <p className="text-center text-sm text-text-secondary">
                Already have an account?{' '}
                <button
                  onClick={() => router.push('/login')}
                  className="text-text-primary font-medium hover:underline transition-colors"
                >
                  Log in
                </button>
              </p>
            </div>
          )}

          {/* ──────────── Step 2: Profile form ──────────── */}
          {step === 2 && (
            <form onSubmit={handleProfileSubmit} className="space-y-4 register-step-animate">
              {/* Full Name */}
              <div>
                <label htmlFor="reg-name" className="block text-sm text-text-secondary mb-1">
                  Full Name <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary/50" />
                  <input
                    id="reg-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Rajesh Kumar"
                    required
                    className="w-full pl-10 pr-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all"
                  />
                </div>
              </div>

              {/* Phone */}
              <div>
                <label htmlFor="reg-phone" className="block text-sm text-text-secondary mb-1">
                  Phone Number <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary/50" />
                  <input
                    id="reg-phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 98765 43210"
                    required
                    className="w-full pl-10 pr-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all"
                  />
                </div>
              </div>

              {/* PAN (optional) */}
              <div>
                <label htmlFor="reg-pan" className="block text-sm text-text-secondary mb-1">
                  PAN Number <span className="text-text-secondary/50 text-xs">(optional)</span>
                </label>
                <div className="relative">
                  <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary/50" />
                  <input
                    id="reg-pan"
                    type="text"
                    value={pan}
                    onChange={(e) => setPan(e.target.value.toUpperCase())}
                    placeholder="ABCDE1234F"
                    maxLength={10}
                    className="w-full pl-10 pr-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all uppercase"
                  />
                </div>
              </div>

              {/* Role selection */}
              <div>
                <label className="block text-sm text-text-secondary mb-2">
                  Your Role <span className="text-red-400">*</span>
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {ROLES.map((r) => {
                    const Icon = r.icon;
                    const isSelected = role === r.value;
                    return (
                      <button
                        key={r.value}
                        type="button"
                        onClick={() => setRole(r.value)}
                        className={`register-role-card ${isSelected ? 'register-role-card-active' : ''}`}
                      >
                        <Icon className="w-5 h-5 mb-1.5" />
                        <span className="text-xs font-medium">{r.label}</span>
                        <span className="text-[10px] text-text-secondary/70 leading-tight mt-0.5 hidden sm:block">{r.description}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Location (optional) */}
              <div>
                <label htmlFor="reg-location" className="block text-sm text-text-secondary mb-1">
                  Location <span className="text-text-secondary/50 text-xs">(optional)</span>
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary/50" />
                  <input
                    id="reg-location"
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="Mumbai, Maharashtra"
                    className="w-full pl-10 pr-3 py-2.5 bg-bg-primary border border-border-subtle rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent text-text-primary placeholder:text-text-secondary/50 transition-all"
                  />
                </div>
              </div>



              {/* Actions */}
              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setStep(1);
                    setError('');
                  }}
                  className="px-4 py-2.5 border border-border-subtle rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-primary transition-all flex items-center gap-1.5"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 py-2.5 bg-accent text-accent-foreground rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-accent-foreground/50 border-t-transparent rounded-full animate-spin" />
                      Completing…
                    </span>
                  ) : (
                    <>
                      Complete Registration
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>

              {/* Login link */}
              <p className="text-center text-xs text-text-secondary pt-1">
                Already have an account?{' '}
                <button
                  onClick={() => router.push('/login')}
                  className="text-text-primary font-medium hover:underline transition-colors"
                  type="button"
                >
                  Log in
                </button>
              </p>
            </form>
          )}
        </div>
      </div>

      <SaasFooter variant="minimal" />

      {/* ── Scoped styles for the registration page ─────────────────── */}
      <style>{`
        /* Card glassmorphism */
        .register-card {
          backdrop-filter: blur(16px);
          box-shadow:
            0 0 0 1px rgba(255,255,255,0.05),
            0 8px 40px rgba(0,0,0,0.08);
        }

        /* Step indicator dots */
        .register-step-dot {
          height: 6px;
          border-radius: 999px;
          transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                      background 0.35s ease;
        }
        .register-step-connector {
          width: 32px;
          height: 2px;
          border-radius: 999px;
          transition: background 0.35s ease;
        }

        /* Step content entrance */
        .register-step-animate {
          animation: registerFadeSlide 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
        }
        @keyframes registerFadeSlide {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        /* Role cards */
        .register-role-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 14px 8px;
          border-radius: 12px;
          border: 1.5px solid var(--border-subtle);
          background: var(--bg-primary);
          cursor: pointer;
          transition: all 0.2s ease;
          text-align: center;
          color: var(--text-secondary);
        }
        .register-role-card:hover {
          border-color: var(--accent);
          color: var(--text-primary);
          transform: translateY(-2px);
          box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        }
        .register-role-card-active {
          border-color: var(--accent) !important;
          background: var(--accent);
          color: var(--accent-foreground) !important;
          box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent);
        }
        .register-role-card-active span {
          color: var(--accent-foreground) !important;
        }
      `}</style>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterContent />
    </Suspense>
  );
}

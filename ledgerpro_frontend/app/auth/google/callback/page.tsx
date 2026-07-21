'use client';

import { useEffect, Suspense, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '../../../auth-context';

function GoogleCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { loginWithGoogleCode, registerWithGoogleCode } = useAuth();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = searchParams.get('code');
    const error = searchParams.get('error');
    // Google returns `state`; sessionStorage is a fallback for older flows
    const authFlow = searchParams.get('state') || sessionStorage.getItem('auth_flow');

    if (error || !code) {
      router.replace('/login?error=oauth_failed');
      return;
    }

    if (authFlow === 'register') {
      sessionStorage.removeItem('auth_flow');
      registerWithGoogleCode(code)
        .then((result) => {
          sessionStorage.setItem('registration_token', result.registration_token);
          sessionStorage.setItem('registration_email', result.email);
          sessionStorage.setItem('registration_name', result.name || '');
          sessionStorage.setItem('registration_avatar', result.avatar || '');
          router.replace('/register?step=profile');
        })
        .catch((err: unknown) => {
          console.error('Google registration failed:', err);
          router.replace('/register?error=registration_failed');
        });
    } else {
      // Login flow (existing behavior)
      loginWithGoogleCode(code)
        .then((result) => {
          if (result.pending_2fa && result.pending_token) {
            sessionStorage.setItem('pending_2fa_token', result.pending_token);
            sessionStorage.setItem('pending_email', result.email || '');
            router.replace('/verify-otp');
          }
        })
        .catch((err: unknown) => {
          console.error('Google login failed:', err);
          router.replace('/login?error=oauth_failed');
        });
    }
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary">
      <div className="flex flex-col items-center gap-4">
        <div className="flex items-center gap-3">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-3 h-3 rounded-full bg-text-primary"
              style={{
                animation: 'dotBounce 1.2s ease-in-out infinite',
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
        </div>
        <p className="text-sm text-text-secondary">Completing Google sign-in…</p>
        <style>{`
          @keyframes dotBounce {
            0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
            40% { transform: scale(1); opacity: 1; }
          }
        `}</style>
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={null}>
      <GoogleCallbackContent />
    </Suspense>
  );
}

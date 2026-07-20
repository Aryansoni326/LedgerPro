'use client';

import Link from 'next/link';
import LedgerProLogo from './components/ledgerpro-logo';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-bg-primary text-text-primary px-6">
      <div className="max-w-md w-full text-center space-y-6">
        <LedgerProLogo size="lg" href="/" className="justify-center" />
        <div className="space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight">404</h1>
          <p className="text-text-secondary text-sm">
            This page could not be found. LedgerPro runs at{' '}
            <span className="font-mono text-text-primary">http://localhost:3001</span>
            .
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link href="/" className="btn-primary text-sm px-4 py-2">
            Go home
          </Link>
          <Link href="/login" className="btn-secondary text-sm px-4 py-2">
            Accountant login
          </Link>
          <Link href="/owner/login" className="btn-secondary text-sm px-4 py-2">
            Owners login
          </Link>
        </div>
      </div>
    </div>
  );
}

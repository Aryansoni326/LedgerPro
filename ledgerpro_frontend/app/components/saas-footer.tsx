'use client';

import React from 'react';
import Link from 'next/link';
import { Mail, MapPin, ArrowUp, ShieldCheck } from 'lucide-react';
import LedgerProLogo from './ledgerpro-logo';

interface SaasFooterProps {
  variant?: 'full' | 'minimal';
}

const LINK_COLUMNS = [
  {
    heading: 'Product',
    links: [
      { href: '/#solutions', label: 'Solutions' },
      { href: '/#features', label: 'Features' },
      { href: '/#how-it-works', label: 'How it works' },
      { href: '/pricing', label: 'Pricing' },
    ],
  },
  {
    heading: 'Built for',
    links: [
      { href: '/#solutions', label: 'CA firms' },
      { href: '/#solutions', label: 'Bookkeeping bureaus' },
      { href: '/#solutions', label: 'Import & export desks' },
      { href: '/#why', label: 'Growing practices' },
    ],
  },
  {
    heading: 'Capabilities',
    links: [
      { href: '/#features', label: 'AI invoice extraction' },
      { href: '/#features', label: 'GST verification' },
      { href: '/#features', label: 'E-way bill tracking' },
      { href: '/#features', label: 'Turnover analytics' },
    ],
  },
  {
    heading: 'Account',
    links: [
      { href: '/register', label: 'Create account' },
      { href: '/login', label: 'Sign in' },
      { href: '/owner/login', label: 'Owner login' },
      { href: '/dashboard', label: 'Dashboard' },
    ],
  },
];

const LEGAL_LINKS = [
  { href: '#', label: 'Privacy' },
  { href: '#', label: 'Terms' },
  { href: '#', label: 'Security' },
];

export default function SaasFooter({ variant = 'full' }: SaasFooterProps) {
  if (variant === 'minimal') {
    return (
      <footer className="bg-bg-primary text-text-secondary transition-colors duration-200 mt-auto">
        <div className="max-w-5xl mx-auto px-6 md:px-8 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <LedgerProLogo size="sm" href="/" />
          <span>&copy; {new Date().getFullYear()} LedgerPro</span>
        </div>
      </footer>
    );
  }

  return (
    <footer className="relative overflow-hidden bg-neutral-50 dark:bg-neutral-950 text-text-primary transition-colors duration-200 border-t border-neutral-200 dark:border-neutral-800">

      <div className="relative max-w-6xl mx-auto px-6 md:px-8 lg:px-12 pt-16 pb-10">
        <div className="grid gap-10 lg:gap-12 lg:grid-cols-[1.4fr_2.6fr] mb-12">
          <div className="space-y-5">
            <LedgerProLogo size="sm" href="/" />
            <p className="text-sm text-text-secondary max-w-xs leading-relaxed">
              AI-driven invoice and GST automation for CA firms and bookkeeping bureaus across India.
              Upload once, verify fast, export filed-ready.
            </p>

            <ul className="space-y-2.5 text-sm text-text-secondary">
              <li className="flex items-center gap-2.5">
                <Mail className="w-4 h-4 shrink-0" strokeWidth={1.75} />
                <a href="mailto:support@ledgerpro.store" className="hover:text-text-primary transition-colors">
                  support@ledgerpro.store
                </a>
              </li>
              <li className="flex items-center gap-2.5">
                <MapPin className="w-4 h-4 shrink-0" strokeWidth={1.75} />
                Ahmedabad, Gujarat, India
              </li>
            </ul>

            <div className="inline-flex items-center gap-2 rounded-full border border-neutral-200 dark:border-neutral-800 bg-bg-primary/70 px-3 py-1.5 text-[11px] text-text-secondary">
              <span className="hero-badge-dot" aria-hidden />
              All systems operational
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
            {LINK_COLUMNS.map((column) => (
              <div key={column.heading} className="space-y-3.5">
                <h4 className="text-[11px] uppercase tracking-[0.18em] text-text-primary font-semibold">
                  {column.heading}
                </h4>
                <ul className="space-y-2.5 text-sm text-text-secondary">
                  {column.links.map((link) => (
                    <li key={`${column.heading}-${link.label}`}>
                      {link.href.startsWith('/#') ? (
                        <a href={link.href} className="hover:text-text-primary transition-colors">
                          {link.label}
                        </a>
                      ) : (
                        <Link href={link.href} className="hover:text-text-primary transition-colors">
                          {link.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="section-divider-glow mb-8" aria-hidden />

        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3 text-sm text-text-secondary">
            <span>&copy; {new Date().getFullYear()} LedgerPro. All rights reserved.</span>
            {LEGAL_LINKS.map((link) => (
              <a key={link.label} href={link.href} className="hover:text-text-primary transition-colors">
                {link.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-2 text-xs text-text-secondary">
              <ShieldCheck className="w-4 h-4" strokeWidth={1.75} />
              GST-compliant · Made in India
            </span>
            <a
              href="#top"
              className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-bg-primary px-3 py-2 text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              Back to top
              <ArrowUp className="w-3.5 h-3.5" strokeWidth={1.75} />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

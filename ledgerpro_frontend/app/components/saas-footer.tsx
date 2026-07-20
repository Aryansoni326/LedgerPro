'use client';

import React from 'react';
import Link from 'next/link';
import LedgerProLogo from './ledgerpro-logo';

interface SaasFooterProps {
  variant?: 'full' | 'minimal';
}

const PRODUCT_LINKS = [
  { href: '/#solutions', label: 'Solutions' },
  { href: '/#features', label: 'Features' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/#how-it-works', label: 'How it Works' },
];

const COMPANY_LINKS = [
  { href: '#', label: 'About' },
  { href: '#', label: 'Contact' },
  { href: '#', label: 'Privacy' },
  { href: '#', label: 'Terms' },
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
    <footer className="bg-neutral-100 dark:bg-neutral-950 text-text-primary pt-16 pb-10 transition-colors duration-200">
      <div className="max-w-6xl mx-auto px-6 md:px-8 lg:px-12 grid md:grid-cols-3 gap-10 mb-12">
        <div className="space-y-4">
          <LedgerProLogo size="sm" href="/" />
          <p className="text-sm text-text-secondary max-w-xs leading-relaxed">
            AI-driven invoice and GST automation for CA firms and bookkeeping bureaus across India.
          </p>
        </div>

        <div className="space-y-3">
          <h4 className="text-xs uppercase tracking-wider text-text-primary font-medium">Product</h4>
          <ul className="space-y-2 text-sm text-text-secondary">
            {PRODUCT_LINKS.map((link) => (
              <li key={link.label}>
                <a href={link.href} className="hover:text-text-primary transition-colors">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-3">
          <h4 className="text-xs uppercase tracking-wider text-text-primary font-medium">Company</h4>
          <ul className="space-y-2 text-sm text-text-secondary">
            {COMPANY_LINKS.map((link) => (
              <li key={link.label}>
                {link.href === '#' ? (
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
      </div>

      <div className="max-w-6xl mx-auto px-6 md:px-8 lg:px-12 pt-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-text-secondary">
        <span>&copy; {new Date().getFullYear()} LedgerPro. All rights reserved.</span>
        <span className="text-xs">Made in India</span>
      </div>
    </footer>
  );
}

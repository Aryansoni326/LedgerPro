'use client';

import React from 'react';
import Link from 'next/link';

interface LedgerProLogoProps {
  size?: 'sm' | 'md' | 'lg';
  showWordmark?: boolean;
  href?: string;
  className?: string;
}

/**
 * Premium Monochrome Logo Mark for LedgerPro.
 * Concept: Three layered, offset ledger sheets representing auditing, pages, and balance.
 * Uses solid fill blocks and cut-out ledger lines for maximum contrast and scalability.
 * Highly visible on both light and dark backgrounds (even at 16x16 tab size).
 */
function LogoMark({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      {/* Page 1 (Back Sheet - Subdued Opacity) */}
      <rect
        x="4"
        y="4"
        width="20"
        height="26"
        rx="3.5"
        className="fill-current opacity-20"
      />

      {/* Page 2 (Middle Sheet - Medium Opacity) */}
      <rect
        x="9"
        y="9"
        width="20"
        height="26"
        rx="3.5"
        className="fill-current opacity-45"
      />

      {/* Page 3 (Front Sheet - Full Solid Block) */}
      <rect
        x="14"
        y="14"
        width="20"
        height="26"
        rx="3.5"
        className="fill-current"
      />

      {/* Ledger record lines cut out of the front sheet */}
      <line
        x1="18"
        y1="20"
        x2="29"
        y2="20"
        className="stroke-bg-secondary"
        strokeWidth="2"
        strokeLinecap="round"
        style={{ stroke: 'var(--bg-secondary, #ffffff)' }}
      />
      <line
        x1="18"
        y1="25"
        x2="29"
        y2="25"
        className="stroke-bg-secondary"
        strokeWidth="2"
        strokeLinecap="round"
        style={{ stroke: 'var(--bg-secondary, #ffffff)' }}
      />
      <line
        x1="18"
        y1="30"
        x2="25"
        y2="30"
        className="stroke-bg-secondary"
        strokeWidth="2"
        strokeLinecap="round"
        style={{ stroke: 'var(--bg-secondary, #ffffff)' }}
      />
    </svg>
  );
}

const sizeMap = {
  sm: { mark: 'w-6 h-6', text: 'text-[15px]' },
  md: { mark: 'w-8 h-8', text: 'text-lg' },
  lg: { mark: 'w-10 h-10', text: 'text-xl' },
};

export default function LedgerProLogo({
  size = 'md',
  showWordmark = true,
  href = '/',
  className = '',
}: LedgerProLogoProps) {
  const s = sizeMap[size];

  const inner = (
    <span className={`inline-flex items-center gap-2.5 text-text-primary ${className}`}>
      <LogoMark className={`${s.mark} shrink-0`} />
      {showWordmark && (
        <span className={`${s.text} font-extrabold tracking-tight leading-none`}>
          <span>Ledger</span>
          <span className="font-light opacity-80">Pro</span>
        </span>
      )}
    </span>
  );

  if (href) {
    return (
      <Link href={href} className="hover:opacity-85 transition-opacity inline-flex" aria-label="LedgerPro home">
        {inner}
      </Link>
    );
  }
  return inner;
}

export { LogoMark };

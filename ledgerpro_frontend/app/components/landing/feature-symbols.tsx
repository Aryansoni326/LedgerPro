'use client';

import React from 'react';
import {
  UploadCloud,
  Cpu,
  FileCheck,
  Globe,
  Truck,
  BarChart3,
  Sparkles,
  FileSpreadsheet,
  ShieldCheck,
} from 'lucide-react';

export type FeatureSymbolKey =
  | 'llm'
  | 'gst'
  | 'trade'
  | 'eway'
  | 'analytics'
  | 'upload'
  | 'ai'
  | 'export'
  | 'gst-compliance';

function MonoBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center justify-center px-3 py-1.5 rounded-lg border border-text-primary/25 bg-bg-primary text-[11px] sm:text-xs font-semibold tracking-wide text-text-primary shadow-sm">
      {children}
    </span>
  );
}

function SymbolCanvas({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`relative w-full h-full min-h-[120px] bg-gradient-to-br from-bg-secondary via-bg-primary to-bg-secondary flex items-center justify-center overflow-hidden ${className}`}
    >
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)',
          backgroundSize: '20px 20px',
        }}
      />
      <div className="relative z-10 flex flex-col items-center justify-center gap-3 px-4 py-5 text-text-primary">
        {children}
      </div>
    </div>
  );
}

const SYMBOLS: Record<FeatureSymbolKey, React.ReactNode> = {
  llm: (
    <>
      <div className="flex items-center gap-4">
        <svg viewBox="0 0 48 56" className="w-10 h-12 text-text-primary" fill="none" aria-hidden>
          <rect x="6" y="4" width="36" height="48" rx="3" stroke="currentColor" strokeWidth="2" />
          <path d="M12 14h24M12 22h20M12 30h24M12 38h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M34 8l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <Cpu className="w-9 h-9 stroke-[1.5]" />
        <Sparkles className="w-7 h-7 stroke-[1.5]" />
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        AI invoice extraction
      </span>
    </>
  ),
  gst: (
    <>
      <div className="flex items-center gap-3">
        <ShieldCheck className="w-11 h-11 stroke-[1.5]" />
        <div className="flex flex-col gap-1.5">
          <MonoBadge>GSTIN</MonoBadge>
          <MonoBadge>18% slab</MonoBadge>
        </div>
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        Real-time verification
      </span>
    </>
  ),
  trade: (
    <>
      <div className="flex items-center gap-4">
        <Globe className="w-10 h-10 stroke-[1.5]" />
        <svg viewBox="0 0 56 32" className="w-14 h-8 text-text-primary" fill="none" aria-hidden>
          <path d="M4 24h48" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 24V14l20-8 20 8v10" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
          <rect x="22" y="10" width="12" height="8" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        Import · export bills
      </span>
    </>
  ),
  eway: (
    <>
      <Truck className="w-14 h-14 stroke-[1.5]" />
      <div className="flex gap-2 flex-wrap justify-center">
        <MonoBadge>E-Way</MonoBadge>
        <MonoBadge>LR No.</MonoBadge>
        <MonoBadge>Distance</MonoBadge>
      </div>
    </>
  ),
  analytics: (
    <>
      <BarChart3 className="w-10 h-10 stroke-[1.5] mb-1" />
      <svg viewBox="0 0 120 40" className="w-28 h-9 text-text-primary" fill="none" aria-hidden>
        <rect x="4" y="22" width="14" height="14" fill="currentColor" opacity="0.35" />
        <rect x="26" y="14" width="14" height="22" fill="currentColor" opacity="0.55" />
        <rect x="48" y="8" width="14" height="28" fill="currentColor" opacity="0.75" />
        <rect x="70" y="4" width="14" height="32" fill="currentColor" />
        <rect x="92" y="12" width="14" height="24" fill="currentColor" opacity="0.6" />
      </svg>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        Turnover & cashflow
      </span>
    </>
  ),
  upload: (
    <>
      <UploadCloud className="w-12 h-12 stroke-[1.5]" />
      <svg viewBox="0 0 48 40" className="w-12 h-10 text-text-primary" fill="none" aria-hidden>
        <path d="M8 32h32" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M24 6v16M18 14l6-6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="12" y="24" width="24" height="8" rx="1" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </>
  ),
  ai: (
    <>
      <div className="flex items-center gap-3">
        <Cpu className="w-10 h-10 stroke-[1.5]" />
        <svg viewBox="0 0 64 48" className="w-16 h-12 text-text-primary" fill="none" aria-hidden>
          <circle cx="12" cy="24" r="4" fill="currentColor" />
          <circle cx="32" cy="12" r="4" fill="currentColor" />
          <circle cx="32" cy="36" r="4" fill="currentColor" />
          <circle cx="52" cy="24" r="4" fill="currentColor" />
          <path d="M16 24h12M36 14l8 8M36 34l8-8" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <Sparkles className="w-8 h-8 stroke-[1.5]" />
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        LLM field mapping
      </span>
    </>
  ),
  export: (
    <>
      <FileSpreadsheet className="w-9 h-9 stroke-[1.5] mb-1" />
      <div className="flex flex-wrap gap-2 justify-center max-w-[220px]">
        <MonoBadge>Tally</MonoBadge>
        <MonoBadge>Excel</MonoBadge>
        <MonoBadge>GSTR</MonoBadge>
        <MonoBadge>SAP</MonoBadge>
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        One-click export
      </span>
    </>
  ),
  'gst-compliance': (
    <>
      <div className="flex items-center gap-3">
        <FileCheck className="w-10 h-10 stroke-[1.5]" />
        <div className="flex flex-col gap-1.5 text-left">
          <MonoBadge>GSTR-1</MonoBadge>
          <MonoBadge>ITC match</MonoBadge>
          <MonoBadge>E-way link</MonoBadge>
        </div>
      </div>
      <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-medium">
        Compliance workflow
      </span>
    </>
  ),
};

export function FeatureSymbolBanner({
  symbol,
  className = '',
}: {
  symbol: FeatureSymbolKey;
  className?: string;
}) {
  return <SymbolCanvas className={className}>{SYMBOLS[symbol]}</SymbolCanvas>;
}

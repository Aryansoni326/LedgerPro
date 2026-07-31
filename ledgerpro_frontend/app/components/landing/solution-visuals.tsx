'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Check, ScanLine, ShieldCheck, Building2 } from 'lucide-react';

/** Shared shell so every visual keeps the same monochrome frame and height. */
function VisualShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative h-[190px] w-full overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/40 p-4">
      {children}
    </div>
  );
}

function useCycle(length: number, ms = 1800) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => (i + 1) % length), ms);
    return () => clearInterval(timer);
  }, [length, ms]);
  return index;
}

/** Workspace switching between client firms. */
export function FirmSwitchVisual() {
  const firms = ['Sharma & Associates', 'Patel Industries', 'Mehta Exports LLP'];
  const active = useCycle(firms.length, 1900);

  return (
    <VisualShell>
      <div className="flex items-center gap-2 mb-3 text-[10px] uppercase tracking-[0.18em] text-text-secondary">
        <Building2 className="w-3.5 h-3.5" strokeWidth={1.75} />
        Client workspaces
      </div>
      <div className="space-y-2">
        {firms.map((firm, i) => {
          const isActive = i === active;
          return (
            <motion.div
              key={firm}
              animate={{
                borderColor: isActive
                  ? 'color-mix(in srgb, var(--text-primary) 55%, transparent)'
                  : 'color-mix(in srgb, var(--text-primary) 12%, transparent)',
                backgroundColor: isActive
                  ? 'color-mix(in srgb, var(--text-primary) 7%, transparent)'
                  : 'transparent',
              }}
              transition={{ duration: 0.35 }}
              className="flex items-center justify-between rounded-lg border px-3 py-2.5"
            >
              <span className={`text-xs ${isActive ? 'text-text-primary font-medium' : 'text-text-secondary'}`}>
                {firm}
              </span>
              {isActive && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="rounded-full bg-accent px-2 py-0.5 text-[9px] font-medium text-accent-foreground"
                >
                  Active
                </motion.span>
              )}
            </motion.div>
          );
        })}
      </div>
    </VisualShell>
  );
}

/** Fields populating themselves instead of being typed by staff. */
export function AutoEntryVisual() {
  const rows = [
    { label: 'Vendor', width: '72%' },
    { label: 'Invoice no.', width: '48%' },
    { label: 'Taxable value', width: '62%' },
    { label: 'CGST / SGST', width: '55%' },
  ];
  const step = useCycle(rows.length + 1, 900);

  return (
    <VisualShell>
      <div className="mb-3 text-[10px] uppercase tracking-[0.18em] text-text-secondary">
        Auto-filled from the bill
      </div>
      <div className="space-y-3">
        {rows.map((row, i) => (
          <div key={row.label} className="space-y-1.5">
            <span className="text-[10px] text-text-secondary">{row.label}</span>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-neutral-200/70 dark:bg-neutral-800/70">
              <motion.span
                className="block h-full rounded-full bg-text-primary/70"
                animate={{ width: i < step ? row.width : '0%' }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
          </div>
        ))}
      </div>
    </VisualShell>
  );
}

/** Compliance checks clearing one after another. */
export function GstCheckVisual() {
  const checks = ['GSTIN active', 'Tax slab matched', 'ITC eligible', 'E-way bill linked'];
  const step = useCycle(checks.length + 1, 800);

  return (
    <VisualShell>
      <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-text-secondary">
        <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.75} />
        Compliance checks
      </div>
      <div className="space-y-2.5">
        {checks.map((check, i) => {
          const done = i < step;
          return (
            <div
              key={check}
              className="flex items-center justify-between rounded-lg border border-neutral-200 dark:border-neutral-800 px-3 py-2"
            >
              <span className={`text-xs ${done ? 'text-text-primary' : 'text-text-secondary'}`}>{check}</span>
              <motion.span
                animate={{ opacity: done ? 1 : 0.2, scale: done ? 1 : 0.85 }}
                transition={{ duration: 0.3 }}
                className="flex h-5 w-5 items-center justify-center rounded-full border border-neutral-300 dark:border-neutral-700"
              >
                <Check className="h-3 w-3 text-text-primary" strokeWidth={2.5} />
              </motion.span>
            </div>
          );
        })}
      </div>
    </VisualShell>
  );
}

/** Turnover trend building up across the quarter. */
export function TurnoverVisual() {
  const bars = [38, 52, 44, 68, 61, 82, 74, 91];
  const [pulse, setPulse] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setPulse((p) => p + 1), 2600);
    return () => clearInterval(timer);
  }, []);

  return (
    <VisualShell>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.18em] text-text-secondary">Turnover trend</span>
        <span className="text-[10px] text-text-secondary">₹ in lakhs</span>
      </div>
      <div className="flex h-[120px] items-end gap-2">
        {bars.map((height, i) => (
          <motion.span
            key={`${pulse}-${i}`}
            className="flex-1 rounded-t-md bg-gradient-to-t from-text-primary/70 to-text-primary/25"
            initial={{ height: '8%' }}
            animate={{ height: `${height}%` }}
            transition={{ duration: 0.6, delay: i * 0.06, ease: 'easeOut' }}
          />
        ))}
      </div>
    </VisualShell>
  );
}

/** Document being scanned and turned into structured fields. */
export function ExtractVisual() {
  const chips = ['Line items', 'HSN codes', 'Tax split', 'Totals'];
  const step = useCycle(chips.length + 1, 850);

  return (
    <VisualShell>
      <div className="grid h-full grid-cols-2 gap-3">
        <div className="relative overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800 bg-bg-primary p-3 scan-sweep">
          <div className="mb-2 flex items-center gap-1.5 text-[9px] text-text-secondary">
            <ScanLine className="h-3 w-3" strokeWidth={1.75} />
            invoice.pdf
          </div>
          <div className="space-y-1.5" aria-hidden>
            {[88, 62, 76, 54, 70, 44, 66].map((w, i) => (
              <span
                key={i}
                className="block h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-800"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        </div>

        <div className="flex flex-col justify-center gap-2">
          {chips.map((chip, i) => (
            <motion.span
              key={chip}
              animate={{
                opacity: i < step ? 1 : 0.2,
                x: i < step ? 0 : -6,
              }}
              transition={{ duration: 0.35 }}
              className="inline-flex items-center gap-2 rounded-full border border-neutral-200 dark:border-neutral-800 bg-bg-primary px-3 py-1.5 text-[10px] text-text-primary"
            >
              <Check className="h-3 w-3" strokeWidth={2.5} />
              {chip}
            </motion.span>
          ))}
        </div>
      </div>
    </VisualShell>
  );
}

/** Reviewing a bill and approving it. */
export function VerifyVisual() {
  const stage = useCycle(3, 1500);

  return (
    <VisualShell>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium text-text-primary">INV-2841</span>
        <motion.span
          animate={{ opacity: 1 }}
          className="rounded-full border border-neutral-200 dark:border-neutral-800 px-2 py-0.5 text-[9px] text-text-secondary"
        >
          {stage === 0 ? 'In review' : stage === 1 ? 'Matched' : 'Approved'}
        </motion.span>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        {[
          ['Taxable', '₹ 12,48,500'],
          ['Total GST', '₹ 2,24,730'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-neutral-200 dark:border-neutral-800 p-2.5">
            <div className="text-[9px] text-text-secondary">{label}</div>
            <div className="text-xs font-semibold text-text-primary tabular-nums mt-0.5">{value}</div>
          </div>
        ))}
      </div>

      <motion.div
        animate={{
          backgroundColor:
            stage === 2 ? 'var(--accent)' : 'color-mix(in srgb, var(--text-primary) 10%, transparent)',
          color: stage === 2 ? 'var(--accent-foreground)' : 'var(--text-secondary)',
        }}
        transition={{ duration: 0.4 }}
        className="flex items-center justify-center gap-2 rounded-lg py-2.5 text-xs font-medium"
      >
        {stage === 2 && <Check className="h-3.5 w-3.5" strokeWidth={2.5} />}
        {stage === 2 ? 'Bill approved' : 'Verify & approve'}
      </motion.div>
    </VisualShell>
  );
}

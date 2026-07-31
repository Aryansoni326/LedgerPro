'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, Cpu, ShieldCheck, FileSpreadsheet, Check } from 'lucide-react';

const STAGES = [
  {
    key: 'upload',
    icon: UploadCloud,
    label: 'Upload',
    caption: 'Purchase bill received',
    detail: 'sharma-textiles-invoice.pdf',
  },
  {
    key: 'extract',
    icon: Cpu,
    label: 'AI extract',
    caption: 'Reading line items & tax fields',
    detail: 'No templates. No manual typing.',
  },
  {
    key: 'verify',
    icon: ShieldCheck,
    label: 'GST verify',
    caption: 'GSTIN and tax slab validated',
    detail: 'Mismatches flagged for review.',
  },
  {
    key: 'export',
    icon: FileSpreadsheet,
    label: 'Export',
    caption: 'Pushed to Tally, Excel & GSTR',
    detail: 'Audit trail saved to Cloud Vault.',
  },
] as const;

const EXTRACTED_FIELDS = [
  { label: 'Vendor', value: 'Sharma Textiles Pvt Ltd' },
  { label: 'Invoice no.', value: 'INV-2841' },
  { label: 'GSTIN', value: '27AABCS1429B1Z5' },
  { label: 'Taxable value', value: '₹ 12,48,500' },
  { label: 'CGST + SGST', value: '₹ 2,24,730' },
];

/** Looping visual of the LedgerPro document pipeline: upload → extract → verify → export. */
export default function PipelineAnimation() {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setStage((s) => (s + 1) % STAGES.length), 2600);
    return () => clearInterval(timer);
  }, []);

  const active = STAGES[stage];
  const revealedFields = stage === 0 ? 0 : stage === 1 ? 3 : EXTRACTED_FIELDS.length;

  return (
    <div className="surface-panel p-5 sm:p-6 w-full">
      <div className="flex items-center justify-between gap-3 mb-5">
        <span className="eyebrow-line">
          <span className="hero-badge-dot" aria-hidden />
          Live pipeline
        </span>
        <span className="text-[11px] text-text-secondary tabular-nums">
          Step {stage + 1} of {STAGES.length}
        </span>
      </div>

      <ol className="grid grid-cols-4 gap-2 mb-6" aria-label="Document processing stages">
        {STAGES.map((item, i) => {
          const isActive = i === stage;
          const isDone = i < stage;
          return (
            <li key={item.key} className="flex flex-col items-center gap-2 text-center">
              <motion.span
                animate={{
                  scale: isActive ? 1.06 : 1,
                  borderColor: isActive
                    ? 'color-mix(in srgb, var(--text-primary) 55%, transparent)'
                    : 'color-mix(in srgb, var(--text-primary) 14%, transparent)',
                }}
                transition={{ duration: 0.3 }}
                className="relative flex h-10 w-10 items-center justify-center rounded-xl border bg-bg-secondary"
              >
                {isDone ? (
                  <Check className="w-4 h-4 text-text-primary" strokeWidth={2.25} />
                ) : (
                  <item.icon
                    className={`w-4 h-4 ${isActive ? 'text-text-primary' : 'text-text-secondary'}`}
                    strokeWidth={1.75}
                  />
                )}
                {isActive && (
                  <motion.span
                    layoutId="pipeline-halo"
                    className="absolute inset-0 rounded-xl ring-glow"
                    aria-hidden
                  />
                )}
              </motion.span>
              <span
                className={`text-[10px] sm:text-[11px] font-medium leading-tight ${
                  isActive ? 'text-text-primary' : 'text-text-secondary'
                }`}
              >
                {item.label}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="relative h-px w-full bg-neutral-200 dark:bg-neutral-800 mb-6 overflow-hidden rounded-full">
        <motion.span
          className="absolute inset-y-0 left-0 bg-text-primary"
          animate={{ width: `${((stage + 1) / STAGES.length) * 100}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="relative rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/60 p-4 overflow-hidden scan-sweep">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-2 w-2 rounded-full bg-neutral-400" aria-hidden />
            <span className="text-[11px] font-medium text-text-secondary truncate">{active.detail}</span>
          </div>
          <div className="space-y-2" aria-hidden>
            {[92, 74, 84, 61, 78, 48].map((w, i) => (
              <motion.div
                key={i}
                className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-800"
                initial={{ opacity: 0.4 }}
                animate={{ opacity: stage === 0 ? 0.4 : 0.85 }}
                transition={{ duration: 0.4, delay: i * 0.04 }}
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-primary p-4">
          <div className="text-[11px] uppercase tracking-widest text-text-secondary mb-3">
            Extracted data
          </div>
          <dl className="space-y-2">
            {EXTRACTED_FIELDS.map((field, i) => (
              <motion.div
                key={field.label}
                animate={{
                  opacity: i < revealedFields ? 1 : 0.25,
                  y: i < revealedFields ? 0 : 4,
                }}
                transition={{ duration: 0.35, delay: i * 0.05 }}
                className="flex items-center justify-between gap-3 text-[11px] sm:text-xs border-b border-border-subtle last:border-0 pb-1.5 last:pb-0"
              >
                <dt className="text-text-secondary shrink-0">{field.label}</dt>
                <dd className="font-medium text-text-primary text-right truncate">{field.value}</dd>
              </motion.div>
            ))}
          </dl>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-3 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/50 px-4 py-3">
        <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-neutral-200 dark:border-neutral-800 bg-bg-primary">
          <active.icon className="w-4 h-4 text-text-primary" strokeWidth={1.75} />
        </span>
        <AnimatePresence mode="wait">
          <motion.p
            key={active.key}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
            className="text-xs sm:text-sm text-text-primary font-medium"
          >
            {active.caption}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
}

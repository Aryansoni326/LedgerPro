'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { SectionHeader, SECTION_SHELL } from './landing-primitives';
import { fadeUp, hoverLift, viewportOnce } from './landing-motion';
import {
  FirmSwitchVisual,
  AutoEntryVisual,
  GstCheckVisual,
  TurnoverVisual,
  ExtractVisual,
  VerifyVisual,
} from './solution-visuals';

const SOLUTIONS = [
  {
    eyebrow: 'Multi-firm workspace',
    title: 'Every client firm in one place',
    description:
      'Add unlimited client firms, switch workspaces instantly, and keep each firm’s invoices, vault and GST data fully isolated.',
    bullets: ['OTP-secured onboarding', 'Switch without logging out', 'Role-based isolation'],
    Visual: FirmSwitchVisual,
    span: 'lg:col-span-3',
  },
  {
    eyebrow: 'Zero manual entry',
    title: 'Stop retyping invoices',
    description:
      'Upload purchase and sales bills in bulk. Vendor details, GST breakup and line items are captured for you.',
    bullets: ['Bulk upload', 'No templates to build'],
    Visual: AutoEntryVisual,
    span: 'lg:col-span-3',
  },
  {
    eyebrow: 'Compliance automation',
    title: 'GST checks that run themselves',
    description:
      'GSTIN status, tax slabs, ITC eligibility and e-way bill links are validated the moment a bill enters the system.',
    bullets: ['Government record checks', 'GSTR-ready reconciliation'],
    Visual: GstCheckVisual,
    span: 'lg:col-span-2',
  },
  {
    eyebrow: 'AI extraction',
    title: 'Reads what your team would',
    description:
      'Tables, handwriting and multi-page PDFs are parsed into structured fields, then routed through your verification flow.',
    bullets: ['Handwriting and scans', 'Multi-page documents'],
    Visual: ExtractVisual,
    span: 'lg:col-span-2',
  },
  {
    eyebrow: 'Bill verification',
    title: 'Approve with an audit trail',
    description:
      'Review extracted data against the original bill, approve in one click, and keep a record of every action taken.',
    bullets: ['Side-by-side review', 'Full action history'],
    Visual: VerifyVisual,
    span: 'lg:col-span-2',
  },
  {
    eyebrow: 'Practice analytics',
    title: 'See the whole practice at a glance',
    description:
      'Track verified bills, firms needing attention and turnover trends across purchase and sales from a single overview.',
    bullets: ['Live turnover trends', 'Attention queue per firm'],
    Visual: TurnoverVisual,
    span: 'lg:col-span-6',
  },
] as const;

export default function LandingSolutions() {
  return (
    <section id="solutions" className={`${SECTION_SHELL} relative`}>
      <div className="relative">
        <SectionHeader
          eyebrow="Built for Indian CA firms"
          title="Solutions that solve real practice problems"
          description="From multi-client billing to GST compliance, LedgerPro replaces spreadsheets and manual follow-ups with one intelligent workspace."
        />

        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-6">
          {SOLUTIONS.map((item, i) => (
            <motion.article
              key={item.title}
              initial="hidden"
              whileInView="visible"
              viewport={viewportOnce}
              variants={fadeUp}
              custom={i * 0.08}
              {...hoverLift}
              className={`${item.span} premium-card p-5 sm:p-6 flex flex-col gap-5 hover:border-neutral-400 dark:hover:border-neutral-600 transition-colors duration-300`}
            >
              <item.Visual />

              <div>
                <span className="badge-pill mb-3">{item.eyebrow}</span>
                <h3 className="text-lg sm:text-xl font-semibold tracking-tight text-text-primary mb-2">
                  {item.title}
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed max-w-[60ch]">
                  {item.description}
                </p>
                <ul className="mt-4 flex flex-wrap gap-2">
                  {item.bullets.map((bullet) => (
                    <li
                      key={bullet}
                      className="inline-flex items-center gap-2 rounded-full border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/50 px-3 py-1 text-[11px] text-text-secondary"
                    >
                      <span className="h-1 w-1 rounded-full bg-text-primary" aria-hidden />
                      {bullet}
                    </li>
                  ))}
                </ul>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}

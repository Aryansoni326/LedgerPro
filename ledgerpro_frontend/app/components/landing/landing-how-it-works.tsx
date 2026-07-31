'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Building2, UploadCloud, ShieldCheck, FileSpreadsheet } from 'lucide-react';
import { SectionHeader, SECTION_SHELL } from './landing-primitives';
import { fadeUp, viewportOnce } from './landing-motion';
import {
  MultiFirmMock,
  AutoInvoiceMock,
  GstComplianceMock,
  BillVerifyMock,
} from './landing-mocks';

const STEPS = [
  {
    step: '01',
    icon: Building2,
    title: 'Add your client firm',
    desc: 'Create a workspace for each client and invite your team. Onboarding is OTP-secured and every firm stays fully isolated.',
    bullets: ['Unlimited firms', 'OTP-verified access', 'Instant firm switch'],
    Mock: MultiFirmMock,
  },
  {
    step: '02',
    icon: UploadCloud,
    title: 'Upload bills in bulk',
    desc: 'Drag in purchase and sales bills, scans, or customs paperwork. PDFs, images and multi-page documents — no templates needed.',
    bullets: ['Drag-and-drop', 'PDFs & scans', 'Handwritten bills'],
    Mock: AutoInvoiceMock,
  },
  {
    step: '03',
    icon: ShieldCheck,
    title: 'Let AI extract and validate',
    desc: 'Line items, tax breakup and vendor details are extracted, then checked against GSTIN records and tax slab rules.',
    bullets: ['Auto field capture', 'ITC & slab checks', 'Flags for review'],
    Mock: GstComplianceMock,
  },
  {
    step: '04',
    icon: FileSpreadsheet,
    title: 'Review, approve and export',
    desc: 'Check extracted data against the original bill, approve in one click, then export to Tally, Excel or GSTR-ready files.',
    bullets: ['Side-by-side review', 'Full audit trail', 'Tally · Excel · GSTR'],
    Mock: BillVerifyMock,
  },
] as const;

const AUTOPLAY_MS = 6000;

export default function LandingHowItWorks() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  const advance = useCallback(() => setActive((i) => (i + 1) % STEPS.length), []);

  useEffect(() => {
    if (paused) return;
    const timer = setInterval(advance, AUTOPLAY_MS);
    return () => clearInterval(timer);
  }, [paused, advance]);

  const current = STEPS[active];
  const CurrentMock = current.Mock;

  return (
    <section id="how-it-works" className={`${SECTION_SHELL} relative overflow-hidden`}>
      <div className="relative">
        <SectionHeader
          eyebrow="How to use it"
          title="From paperwork to filed-ready in four steps"
          description="Set up once, then run your whole practice through the same flow every week."
        />

        <div
          className="grid lg:grid-cols-2 gap-5 lg:gap-8 items-start"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          <motion.ol
            initial="hidden"
            whileInView="visible"
            viewport={viewportOnce}
            variants={fadeUp}
            className="space-y-2"
          >
            {STEPS.map((item, i) => {
              const isActive = i === active;
              return (
                <li key={item.step}>
                  <button
                    type="button"
                    onClick={() => setActive(i)}
                    aria-current={isActive ? 'step' : undefined}
                    className={`w-full text-left rounded-xl border px-4 py-3 transition-all duration-300 ${
                      isActive
                        ? 'border-neutral-300 dark:border-neutral-600 bg-bg-primary shadow-[0_8px_28px_rgb(0,0,0,0.06)]'
                        : 'border-transparent bg-transparent hover:bg-bg-secondary/40'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <item.icon
                        className={`w-4 h-4 shrink-0 ${isActive ? 'text-text-primary' : 'text-text-secondary'}`}
                        strokeWidth={1.75}
                      />
                      <span className="text-[11px] font-semibold tracking-[0.18em] text-text-secondary tabular-nums">
                        {item.step}
                      </span>
                      <h3
                        className={`text-sm sm:text-base font-semibold tracking-tight ${
                          isActive ? 'text-text-primary' : 'text-text-secondary'
                        }`}
                      >
                        {item.title}
                      </h3>
                    </div>

                    <AnimatePresence initial={false}>
                      {isActive && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3, ease: 'easeOut' }}
                          className="overflow-hidden"
                        >
                          <p className="text-sm text-text-secondary leading-relaxed mt-2.5 pl-7 max-w-[56ch]">
                            {item.desc}
                          </p>
                          <ul className="mt-3 pl-7 flex flex-wrap gap-1.5">
                            {item.bullets.map((bullet) => (
                              <li
                                key={bullet}
                                className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 dark:border-neutral-800 px-2.5 py-0.5 text-[11px] text-text-secondary"
                              >
                                {bullet}
                              </li>
                            ))}
                          </ul>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {isActive && (
                      <div className="mt-3 h-0.5 w-full rounded-full bg-neutral-200/70 dark:bg-neutral-800/70 overflow-hidden">
                        <motion.span
                          key={`${item.step}-${paused}`}
                          className="block h-full bg-text-primary"
                          initial={{ width: '0%' }}
                          animate={{ width: paused ? '35%' : '100%' }}
                          transition={{ duration: paused ? 0.3 : AUTOPLAY_MS / 1000, ease: 'linear' }}
                        />
                      </div>
                    )}
                  </button>
                </li>
              );
            })}
          </motion.ol>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={viewportOnce}
            variants={fadeUp}
            custom={0.12}
            className="lg:sticky lg:top-24"
          >
            <div className="surface-panel p-4 sm:p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="flex gap-1.5" aria-hidden>
                  <span className="w-2 h-2 rounded-full bg-neutral-400/80" />
                  <span className="w-2 h-2 rounded-full bg-neutral-500/80" />
                  <span className="w-2 h-2 rounded-full bg-neutral-600/80" />
                </div>
                <span className="text-[10px] text-text-secondary ml-1">
                  app.ledgerpro.store · step {current.step}
                </span>
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={current.step}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="rounded-lg bg-bg-primary p-3 sm:p-4"
                >
                  <CurrentMock embedded />
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

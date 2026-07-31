'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { XCircle, CheckCircle2, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { SectionHeader, SECTION_SHELL } from './landing-primitives';
import { fadeUp, viewportOnce } from './landing-motion';

const PAINS = [
  'Staff retype every purchase and sales bill by hand',
  'GSTIN and tax slabs checked manually, one vendor at a time',
  'Client files scattered across email, WhatsApp and folders',
  'Reconciliation mismatches surface only at filing deadlines',
  'Adding a new client means adding another person',
];

const GAINS = [
  'Bulk upload bills once — AI extracts every line item',
  'GSTIN, tax slab and ITC validated automatically on ingest',
  'Every client firm isolated in one searchable workspace',
  'Mismatches flagged the moment a bill enters the system',
  'Handle more clients with the team you already have',
];

const IMPACT = [
  { value: 18, suffix: ' hrs', label: 'Manual data entry removed each week' },
  { value: 99.8, suffix: '%', label: 'Fields extracted without correction', decimals: 1 },
  { value: 12, suffix: ' sec', label: 'To reconcile a 500-invoice batch' },
];

function CountUp({ value, suffix, decimals = 0 }: { value: number; suffix: string; decimals?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const duration = 1200;
    const start = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      // easeOutCubic keeps the number settling smoothly instead of snapping
      setDisplay(value * (1 - Math.pow(1 - progress, 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [inView, value]);

  return (
    <span ref={ref} className="stat-figure">
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

export default function LandingProblem() {
  return (
    <section id="why" className={`${SECTION_SHELL} relative`}>
      <div className="absolute inset-0 landing-dot-pattern pointer-events-none opacity-40" aria-hidden />

      <div className="relative">
        <SectionHeader
          eyebrow="The problem we solve"
          title="Your team is doing work software should do"
          description="Most practices lose their week to typing, checking and chasing paperwork. LedgerPro removes that layer so your people work on advisory, not admin."
        />

        <div className="grid md:grid-cols-2 gap-5 lg:gap-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={viewportOnce}
            variants={fadeUp}
            className="premium-card p-6 sm:p-7"
          >
            <span className="badge-pill mb-5">Today, without LedgerPro</span>
            <ul className="space-y-3.5">
              {PAINS.map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm text-text-secondary leading-relaxed">
                  <XCircle className="w-4 h-4 mt-0.5 shrink-0 text-text-secondary/70" strokeWidth={1.75} />
                  {item}
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={viewportOnce}
            variants={fadeUp}
            custom={0.12}
            className="premium-card p-6 sm:p-7 relative overflow-hidden border-neutral-300 dark:border-neutral-700"
          >
            <div className="absolute inset-x-0 top-0 h-px beam-line" aria-hidden />
            <span className="badge-pill mb-5">With LedgerPro</span>
            <ul className="space-y-3.5">
              {GAINS.map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm text-text-primary leading-relaxed">
                  <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-text-primary" strokeWidth={1.75} />
                  {item}
                </li>
              ))}
            </ul>
          </motion.div>
        </div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
          custom={0.2}
          className="mt-6 surface-panel p-6 sm:p-8 grid sm:grid-cols-3 gap-6 text-center"
        >
          {IMPACT.map((stat) => (
            <div key={stat.label} className="flex flex-col items-center gap-2">
              <CountUp value={stat.value} suffix={stat.suffix} decimals={stat.decimals ?? 0} />
              <span className="text-xs sm:text-sm text-text-secondary max-w-[24ch] leading-relaxed">
                {stat.label}
              </span>
            </div>
          ))}
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
          custom={0.26}
          className="mt-6 flex justify-center"
        >
          <Link href="/register" className="group btn-secondary text-sm">
            See how it works for your practice
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}

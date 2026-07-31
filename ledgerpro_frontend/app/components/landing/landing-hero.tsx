'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, ShieldCheck, Zap, Clock } from 'lucide-react';
import { DashboardShowcase } from './landing-mocks';
import PipelineAnimation from './pipeline-animation';

const ANIMATED_QUOTES = [
  'Invoices extracted · verified · exported in one click.',
  'GST validated · reconciled · filed-ready.',
  'Reconciliations done in minutes, not days.',
  'One workspace for every client firm.',
  'AI-powered extraction. Zero manual entry.',
  'Audit-ready exports to Tally, Excel & GSTR.',
];

const HERO_STATS = [
  { icon: Zap, value: '99.8%', label: 'Extraction accuracy' },
  { icon: Clock, value: '18 hrs', label: 'Saved every week' },
  { icon: ShieldCheck, value: '0 errors', label: 'GST mismatch target' },
];

const WORKS_WITH = [
  'Tally',
  'Excel',
  'GSTR-1',
  'GSTR-3B',
  'E-way Bill',
  'Bills of Entry',
  'QuickBooks',
  'SAP',
  'Scanned PDFs',
  'Cloud Vault',
];

export default function LandingHero() {
  const [quoteIndex, setQuoteIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setQuoteIndex((i) => (i + 1) % ANIMATED_QUOTES.length);
    }, 3600);
    return () => clearInterval(interval);
  }, []);

  const currentQuote = ANIMATED_QUOTES[quoteIndex];

  return (
    <section className="relative z-10 pt-24 pb-10 md:pt-28 md:pb-14 px-6 md:px-8 lg:px-12 overflow-hidden">
      <div className="absolute inset-0 landing-aurora pointer-events-none" aria-hidden />

      <div className="relative max-w-3xl mx-auto flex flex-col items-center text-center">
        <motion.span
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="hero-badge mb-6"
        >
          <span className="hero-badge-dot" aria-hidden />
          For Indian CA firms
        </motion.span>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.06 }}
          className="hero-headline"
        >
          <span className="hero-headline-gradient">Autonomous accounting</span>
          <span className="block hero-headline-sub">for Indian CA firms & accountants.</span>
        </motion.h1>

        <div className="relative h-10 sm:h-11 w-full max-w-xl mt-5 mb-5 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.p
              key={currentQuote}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -14 }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
              className="hero-quote-text"
            >
              <span className="hero-quote-mark" aria-hidden>&ldquo;</span>
              {currentQuote}
              <span className="hero-quote-mark" aria-hidden>&rdquo;</span>
            </motion.p>
          </AnimatePresence>
        </div>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.18 }}
          className="hero-subtext"
        >
          Multi-client billing, <span className="hero-subtext-mono">GST</span>, and{' '}
          <span className="hero-subtext-mono">e-way bills</span> in one workspace.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.24 }}
          className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto mb-3"
        >
          <Link href="/register" className="group btn-primary text-sm px-6 py-2.5 w-full sm:w-auto">
            Start free trial
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link href="/register" className="btn-secondary text-sm px-6 py-2.5 w-full sm:w-auto">
            Book a demo
          </Link>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.4 }}
          className="text-[11px] uppercase tracking-[0.18em] text-text-secondary/80 mb-7 font-medium"
        >
          14-day trial · No card · GST-compliant
        </motion.p>

        <motion.ul
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.32 }}
          className="grid grid-cols-3 gap-3 w-full max-w-xl mb-8"
        >
          {HERO_STATS.map((stat) => (
            <li
              key={stat.label}
              className="surface-panel px-3 py-4 flex flex-col items-center gap-1.5"
            >
              <stat.icon className="w-4 h-4 text-text-secondary" strokeWidth={1.75} />
              <span className="text-lg sm:text-xl font-semibold tracking-tight tabular-nums text-text-primary">
                {stat.value}
              </span>
              <span className="text-[10px] sm:text-[11px] text-text-secondary leading-tight text-center">
                {stat.label}
              </span>
            </li>
          ))}
        </motion.ul>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.34 }}
        className="relative max-w-6xl mx-auto grid lg:grid-cols-5 gap-5 lg:gap-6 items-start"
      >
        <div className="lg:col-span-3">
          <div className="hidden sm:block">
            <DashboardShowcase />
          </div>
          <div className="sm:hidden">
            <DashboardShowcase compact />
          </div>
        </div>
        <div className="lg:col-span-2">
          <PipelineAnimation />
        </div>
      </motion.div>

      <div className="relative max-w-5xl mx-auto mt-10">
        <p className="text-center text-[11px] uppercase tracking-[0.18em] text-text-secondary mb-4">
          Works with the tools your practice already runs on
        </p>
        <div className="marquee-mask overflow-hidden">
          <div className="marquee-track gap-3">
            {[...WORKS_WITH, ...WORKS_WITH].map((item, i) => (
              <span
                key={`${item}-${i}`}
                className="shrink-0 rounded-full border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/60 px-4 py-1.5 text-xs font-medium text-text-secondary"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { DashboardShowcase } from './landing-mocks';

const ANIMATED_QUOTES = [
  'Invoices extracted · verified · exported in one click.',
  'GST validated · reconciled · filed-ready.',
  'Reconciliations done in minutes, not days.',
  'One workspace for every client firm.',
  'AI-powered extraction. Zero manual entry.',
  'Audit-ready exports to Tally, Excel & GSTR.',
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
    <section className="relative z-10 pt-24 pb-14 md:pt-28 md:pb-20 px-6 md:px-8 lg:px-12">
      <div className="max-w-3xl mx-auto flex flex-col items-center text-center">
        <motion.span
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="hero-badge mb-8"
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

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.12 }}
          className="hero-tagline mb-6"
        >
          Ledger automation for your practice.
        </motion.p>

        <div className="relative h-10 sm:h-11 w-full max-w-xl mb-6 overflow-hidden">
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
          className="text-[11px] uppercase tracking-[0.18em] text-text-secondary/80 mb-6 font-medium"
        >
          14-day trial · No card · GST-compliant
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.55, delay: 0.32 }}
          whileHover={{ boxShadow: '0 0 48px rgba(0, 0, 0, 0.06)' }}
          className="w-full max-w-3xl rounded-2xl transition-shadow duration-300 dark:hover:shadow-[0_0_48px_rgba(255,255,255,0.04)]"
        >
          <div className="hidden sm:block">
            <DashboardShowcase />
          </div>
          <div className="sm:hidden">
            <DashboardShowcase compact />
          </div>
        </motion.div>
      </div>
    </section>
  );
}

'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, ShieldCheck, Clock, Users } from 'lucide-react';
import { fadeUp, viewportOnce } from './landing-motion';

const ASSURANCES = [
  { icon: Clock, text: '14-day free trial' },
  { icon: ShieldCheck, text: 'GST-compliant by design' },
  { icon: Users, text: 'Unlimited client firms' },
];

export default function LandingCta() {
  return (
    <section className="relative z-10 px-6 md:px-8 lg:px-12 py-12 md:py-16">
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={fadeUp}
        className="relative max-w-5xl mx-auto overflow-hidden rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-bg-primary px-6 py-12 sm:px-12 sm:py-16 text-center"
      >
        <div className="absolute inset-0 landing-aurora pointer-events-none" aria-hidden />
        <div className="absolute inset-x-0 top-0 h-px beam-line" aria-hidden />

        <div className="relative flex flex-col items-center">
          <span className="badge-pill mb-6">Start today</span>

          <h2 className="text-3xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-text-primary mb-5 max-w-[20ch]">
            Give your practice its week back
          </h2>

          <p className="text-base md:text-lg text-text-secondary leading-relaxed max-w-[60ch] mb-8">
            Set up your first client firm, upload a folder of bills, and watch LedgerPro extract,
            validate and export them before your tea gets cold.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto mb-8">
            <Link href="/register" className="group btn-primary text-sm px-7 py-3 w-full sm:w-auto">
              Start free trial
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link href="/login" className="btn-secondary text-sm px-7 py-3 w-full sm:w-auto">
              Sign in to your workspace
            </Link>
          </div>

          <ul className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
            {ASSURANCES.map((item) => (
              <li key={item.text} className="flex items-center gap-2 text-xs sm:text-sm text-text-secondary">
                <item.icon className="w-4 h-4" strokeWidth={1.75} />
                {item.text}
              </li>
            ))}
          </ul>
        </div>
      </motion.div>
    </section>
  );
}

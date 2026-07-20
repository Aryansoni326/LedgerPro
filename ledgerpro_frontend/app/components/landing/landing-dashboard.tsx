'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, Check, LayoutDashboard, FileText, Globe, Truck, Database } from 'lucide-react';
import { fadeUp, viewportOnce } from './landing-motion';
import { SECTION_SHELL } from './landing-primitives';

const DASHBOARD_FEATURES = [
  { icon: LayoutDashboard, text: 'Firm overview with purchase vs sales turnover charts' },
  { icon: FileText, text: 'Invoice pipeline | upload, extract, verify, and export' },
  { icon: Globe, text: 'GST validation with real-time GSTIN checks' },
  { icon: Truck, text: 'Import-export documents and e-way bill management' },
  { icon: Database, text: 'Cloud vault | year-wise document archive per client' },
  { icon: Check, text: 'Switch between client firms from one secure workspace' },
];

function ChecklistItem({ icon: Icon, text, index }: { icon: typeof LayoutDashboard; text: string; index: number }) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={viewportOnce}
      transition={{ duration: 0.45, delay: index * 0.05 }}
      className="flex items-start gap-3 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/40 shadow-[0_2px_8px_rgba(0,0,0,0.04)] dark:shadow-none"
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent mt-0.5">
        <Icon className="h-4 w-4" strokeWidth={2} />
      </span>
      <span className="text-xs text-text-primary leading-relaxed font-medium">
        {text}
      </span>
    </motion.li>
  );
}

export default function LandingDashboard() {
  return (
    <section id="dashboard-preview" className={SECTION_SHELL}>
      <div className="flex flex-col items-center text-center max-w-5xl mx-auto">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
          className="flex flex-col items-center"
        >
          <span className="badge-pill mb-4">Inside the app</span>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tight mt-2 mb-4 text-text-primary">
            Advanced, user-friendly dashboard
          </h2>
          <p className="text-text-secondary text-base leading-relaxed mb-8 max-w-[75ch]">
            Everything your practice needs | overview analytics, invoice processing, trade documents, e-way bills, and secure cloud vault | in one clean interface designed for Indian accountants.
          </p>
        </motion.div>

        <div className="w-full mb-8">
          <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 text-left">
            {DASHBOARD_FEATURES.map((item, i) => (
              <ChecklistItem key={item.text} icon={item.icon} text={item.text} index={i} />
            ))}
          </ul>
        </div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
          custom={0.15}
          className="flex flex-col sm:flex-row sm:items-center gap-4 mb-10 justify-center"
        >
          <Link href="/register" className="group btn-primary">
            Explore the App
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <button
            type="button"
            disabled
            className="text-sm text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Video tour coming soon"
          >
            Watch a 2-min tour
          </button>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
          custom={0.2}
          className="w-full relative aspect-[16/10] rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/40 overflow-hidden shadow-2xl"
        >
          <img
            src="/images/landing/dashboard-showcase.png"
            alt="LedgerPro dashboard preview"
            className="w-full h-full object-cover"
          />
        </motion.div>
      </div>
    </section>
  );
}

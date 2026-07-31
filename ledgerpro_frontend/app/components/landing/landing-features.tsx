'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, FileCheck, Globe, CheckCircle2, BarChart3, Lock } from 'lucide-react';
import { SectionHeader, SECTION_SHELL } from './landing-primitives';
import { viewportOnce } from './landing-motion';

const FEATURES = [
  {
    icon: Cpu,
    title: 'LLM invoice extraction',
    desc: 'Structured tables, handwriting and multi-currency values mapped without templates.',
    metric: 'Accuracy',
    fill: 99,
    value: '99.8%',
  },
  {
    icon: FileCheck,
    title: 'GST verification',
    desc: 'Vendor GSTIN status, slab rules and ITC claims validated in real time.',
    metric: 'Checks per bill',
    fill: 84,
    value: '12',
  },
  {
    icon: Globe,
    title: 'Import-export tracking',
    desc: 'Bills of entry and shipping details matched against declared tax rates.',
    metric: 'Docs automated',
    fill: 72,
    value: '14k+',
  },
  {
    icon: CheckCircle2,
    title: 'E-way bills',
    desc: 'Transport distance, vehicle details and registry files generated in seconds.',
    metric: 'Generation time',
    fill: 91,
    value: '8 sec',
  },
  {
    icon: BarChart3,
    title: 'Turnover analytics',
    desc: 'Cashflow analysis, tax projections and billing anomaly detection.',
    metric: 'Refresh',
    fill: 96,
    value: 'Live',
  },
  {
    icon: Lock,
    title: 'Secure document vault',
    desc: 'Year-wise archive per firm with encrypted storage and role-based access.',
    metric: 'Retention',
    fill: 88,
    value: '8 yrs',
  },
];

export default function LandingFeatures() {
  return (
    <section id="features" className={`${SECTION_SHELL} bg-bg-secondary/30`}>
      <SectionHeader
        eyebrow="Capabilities"
        title="Engineered for accuracy"
        description="The engine behind every workflow — precise, auditable and built for complex Indian corporate invoicing."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px overflow-hidden rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-neutral-200 dark:bg-neutral-800">
        {FEATURES.map((feature, i) => (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={viewportOnce}
            transition={{ duration: 0.45, delay: i * 0.06 }}
            className="group relative bg-bg-primary p-6 transition-colors duration-300 hover:bg-bg-secondary/60"
          >
            <div className="flex items-start gap-3 mb-3">
              <feature.icon
                className="w-[18px] h-[18px] mt-0.5 text-text-secondary group-hover:text-text-primary transition-colors"
                strokeWidth={1.75}
              />
              <h3 className="text-sm font-semibold tracking-tight text-text-primary">{feature.title}</h3>
            </div>

            <p className="text-sm text-text-secondary leading-relaxed mb-5 max-w-[46ch]">{feature.desc}</p>

            <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.16em] text-text-secondary mb-2">
              <span>{feature.metric}</span>
              <span className="text-text-primary font-semibold tabular-nums normal-case tracking-normal text-xs">
                {feature.value}
              </span>
            </div>
            <div className="h-1 w-full overflow-hidden rounded-full bg-neutral-200/80 dark:bg-neutral-800/80">
              <motion.span
                className="block h-full rounded-full bg-neutral-800 dark:bg-neutral-200 group-hover:bg-neutral-950 dark:group-hover:bg-white transition-colors"
                initial={{ width: 0 }}
                whileInView={{ width: `${feature.fill}%` }}
                viewport={viewportOnce}
                transition={{ duration: 0.8, delay: 0.2 + i * 0.06, ease: 'easeOut' }}
              />
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

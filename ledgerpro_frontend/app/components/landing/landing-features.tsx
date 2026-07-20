'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, FileCheck, Globe, CheckCircle2, BarChart3 } from 'lucide-react';
import { SectionHeader, PremiumCard, SECTION_SHELL } from './landing-primitives';
import { staggerContainer, viewportOnce } from './landing-motion';

const FEATURES = [
  {
    span: 'md:col-span-2 lg:col-span-4 xl:col-span-4',
    icon: Cpu,
    title: 'LLM Invoice Extraction',
    desc: 'Reads structured tables, handwritten bills, and multi-currency values. Maps raw rows to inventory SKUs with zero templates.',
    foot: '99.8% extraction accuracy',
  },
  {
    span: 'md:col-span-1 lg:col-span-2 xl:col-span-2',
    icon: FileCheck,
    title: 'GST Verification',
    desc: 'Validates vendor GSTIN status, tax slab rules, and match claims in real time.',
    foot: 'Tax reconciliation',
  },
  {
    span: 'md:col-span-1 lg:col-span-2 xl:col-span-2',
    icon: Globe,
    title: 'Import-Export tracking',
    desc: 'Bills of entry and shipping details matched to verify tax rates and logistics data.',
    foot: 'Cross-border invoicing',
  },
  {
    span: 'md:col-span-1 lg:col-span-2 xl:col-span-2',
    icon: CheckCircle2,
    title: 'E-Way Bills',
    desc: 'Verify transport distances, generate vehicle details, and submit registry files in seconds.',
    foot: 'Compliance check',
  },
  {
    span: 'md:col-span-1 lg:col-span-2 xl:col-span-2',
    icon: BarChart3,
    title: 'Turnover Analytics',
    desc: 'Instant cashflow analysis, tax projections, and billing anomaly detection.',
    foot: 'Real-time reports',
  },
];

export default function LandingFeatures() {
  return (
    <section id="features" className={`${SECTION_SHELL} bg-bg-secondary/30`}>
      <SectionHeader
        eyebrow="Capabilities"
        title="Built for high accuracy"
        description="Robust tools for complex corporate invoicing and tax auditing."
      />

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={staggerContainer}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 xl:grid-cols-6 gap-6 lg:gap-8"
      >
        {FEATURES.map((card, i) => (
          <PremiumCard
            key={card.title}
            icon={card.icon}
            title={card.title}
            description={card.desc}
            footer={card.foot}
            colSpan={card.span}
            className={i === 0 ? '' : ''}
          />
        ))}
      </motion.div>
    </section>
  );
}

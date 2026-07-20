'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { UploadCloud, Cpu, FileSpreadsheet } from 'lucide-react';
import { LANDING_PHOTOS } from './landing-photos';
import { SectionHeader, SECTION_SHELL } from './landing-primitives';
import { ImageFrame } from './landing-photo';
import { fadeUp, hoverLift, viewportOnce } from './landing-motion';

const STEPS = [
  {
    step: '01',
    icon: UploadCloud,
    title: 'Upload Invoices',
    desc: 'Drag-and-drop folders, upload scans, or forward billing emails. Supports PDFs, images, and customs shipping documents.',
    image: LANDING_PHOTOS.steps.upload,
    alt: 'Uploading invoice documents to the cloud',
  },
  {
    step: '02',
    icon: Cpu,
    title: 'AI Processing',
    desc: 'Our specialized LLM extracts metadata, matches items, and cross-references GST registration databases for compliance.',
    image: LANDING_PHOTOS.steps.ai,
    alt: 'AI processing invoice data on laptop',
  },
  {
    step: '03',
    icon: FileSpreadsheet,
    title: 'Sync & Export',
    desc: 'Export reconciled transactions to Tally, SAP, or QuickBooks, and download compliant GSTR return files in one click.',
    image: LANDING_PHOTOS.steps.export,
    alt: 'Exporting reconciled data to accounting software',
  },
];

export default function LandingHowItWorks() {
  return (
    <section id="how-it-works" className={SECTION_SHELL}>
      <SectionHeader
        eyebrow="Process overview"
        title="How it works"
        description="Three simple steps to automate your accounting workflow from upload to export."
      />

      <div className="relative grid md:grid-cols-3 gap-8 lg:gap-10 mt-4">
        <div
          className="hidden md:block absolute top-[140px] left-[16.67%] right-[16.67%] h-px bg-neutral-200 dark:bg-neutral-800"
          aria-hidden
        />

        {STEPS.map((card, i) => (
          <motion.article
            key={card.step}
            initial="hidden"
            whileInView="visible"
            viewport={viewportOnce}
            variants={fadeUp}
            custom={i * 0.1}
            className="group relative"
          >
            <motion.div
              {...hoverLift}
              className="premium-card overflow-hidden hover:shadow-[0_12px_40px_rgb(0,0,0,0.08)] transition-shadow duration-300"
            >
              <ImageFrame src={card.image} alt={card.alt} gradient>
                <span className="absolute top-4 left-4 flex h-10 w-10 items-center justify-center rounded-full border border-neutral-200 dark:border-neutral-800 bg-bg-primary/90 backdrop-blur-sm text-xs font-semibold text-text-primary">
                  {card.step}
                </span>
              </ImageFrame>

              <div className="p-5 sm:p-6">
                <div className="flex items-center gap-2.5 mb-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 dark:border-neutral-800 bg-bg-secondary group-hover:scale-105 transition-transform">
                    <card.icon className="w-4 h-4 text-text-secondary" strokeWidth={1.75} />
                  </span>
                  <h3 className="text-base font-semibold tracking-tight">{card.title}</h3>
                </div>
                <p className="text-text-secondary text-sm leading-relaxed max-w-[65ch]">{card.desc}</p>
              </div>
            </motion.div>
          </motion.article>
        ))}
      </div>
    </section>
  );
}

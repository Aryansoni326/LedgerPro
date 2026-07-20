'use client';

import React from 'react';
import { LANDING_PHOTOS } from './landing-photos';
import { SectionHeader, SolutionRow, SECTION_SHELL } from './landing-primitives';

const SOLUTIONS = [
  {
    eyebrow: 'Multi-firm workspace',
    title: 'Manage every client firm from one dashboard',
    description:
      'Running multiple billing entities is essential for CA practices. Add unlimited client firms, switch workspaces instantly, and keep every firm\'s invoices, vault, and GST data fully isolated.',
    bullets: [
      'OTP-secured firm onboarding',
      'Switch firms without logging out',
      'Firm-level data isolation with roles',
    ],
    image: LANDING_PHOTOS.solutions.multiFirm,
    imageAlt: 'CA firm team collaborating on client accounts',
    imagePosition: 'right' as const,
  },
  {
    eyebrow: 'Zero manual entry',
    title: 'Stop retyping invoices | work hassle-free',
    description:
      'Upload purchase and sales bills in bulk. AI extracts vendor details, GST breakup, and line items automatically so your staff focuses on review, not data entry.',
    image: LANDING_PHOTOS.solutions.invoices,
    imageAlt: 'Purchase invoices and receipts on desk',
    imagePosition: 'left' as const,
  },
  {
    eyebrow: 'Compliance automation',
    title: 'Fully automated GST & document workflow',
    description:
      'Automate GST validation, import-export matching, e-way bill tracking, and audit-ready exports | the recurring work that eats 90% of your team\'s week.',
    bullets: [
      'Auto GSTIN validation against government records',
      'GSTR-ready purchase vs sales reconciliation',
      'E-way bill linking and cloud vault archive',
    ],
    image: LANDING_PHOTOS.solutions.gst,
    imageAlt: 'GST tax forms and calculator on desk',
    imagePosition: 'right' as const,
  },
  {
    eyebrow: 'Team productivity',
    title: 'Small team, more output',
    description:
      'See verified bills, firms needing attention, and turnover trends across purchase and sales | all from the overview tab. Handle more clients without hiring.',
    image: LANDING_PHOTOS.solutions.analytics,
    imageAlt: 'Accountant reviewing firm turnover and productivity metrics on screen',
    imagePosition: 'left' as const,
  },
  {
    eyebrow: 'AI extraction',
    title: 'Automate invoice extraction',
    description:
      'Upload PDFs or images once. LedgerPro extracts line items, tax fields, and vendor metadata, then routes bills through your verification workflow.',
    bullets: [
      'Bulk upload for purchase and sales invoices',
      'AI extraction for tables, handwriting, and multi-page PDFs',
      'One-click export to Tally, Excel, or GSTR',
    ],
    image: LANDING_PHOTOS.solutions.extract,
    imageAlt: 'Accountant scanning and digitizing invoices for AI extraction',
    imagePosition: 'right' as const,
  },
  {
    eyebrow: 'Bill verification',
    title: 'Verify bills like a pro',
    description:
      'Review extracted data side-by-side with originals. Approve bills, flag mismatches, and maintain a complete audit trail for every action.',
    image: LANDING_PHOTOS.solutions.verify,
    imageAlt: 'Professional reviewing GST bills for approval',
    imagePosition: 'left' as const,
  },
];

export default function LandingSolutions() {
  return (
    <section id="solutions" className="relative z-10">
      <div className="absolute inset-0 landing-dot-pattern pointer-events-none opacity-60" aria-hidden />
      <div className={SECTION_SHELL}>
        <SectionHeader
          eyebrow="Built for Indian CA firms"
          title="Solutions that solve real practice problems"
          description="From multi-client billing to GST compliance | LedgerPro replaces spreadsheets and manual follow-ups with one intelligent workspace."
        />

        {SOLUTIONS.map((item, i) => (
          <SolutionRow
            key={item.title}
            index={i}
            eyebrow={item.eyebrow}
            title={item.title}
            description={item.description}
            bullets={item.bullets}
            imageSrc={item.image}
            imageAlt={item.imageAlt}
            imagePosition={item.imagePosition}
            layout="split"
          />
        ))}
      </div>
    </section>
  );
}

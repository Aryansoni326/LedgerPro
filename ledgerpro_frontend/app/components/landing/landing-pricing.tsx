'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';
import { SectionHeader, SECTION_SHELL } from './landing-primitives';
import { fadeUp, staggerContainer, hoverLift, viewportOnce } from './landing-motion';

const PRICING_PLANS = [
  {
    name: 'Free',
    price: '0',
    period: '/month',
    tagline: 'Try LedgerPro with one firm',
    features: [
      '1 client firm',
      '25 documents per month',
      '10 AI queries (read-only insights)',
      'No API or agent access',
    ],
    cta: 'Start free',
    highlighted: false,
  },
  {
    name: 'Starter',
    price: '2,499',
    period: '/month',
    tagline: 'For solo CAs getting started',
    features: [
      'Up to 3 client firms',
      '500 documents per month',
      'GST validation & GSTR export',
      'Email support',
    ],
    cta: 'Start your free trial',
    highlighted: false,
  },
  {
    name: 'Growth',
    price: '4,999',
    period: '/month',
    tagline: 'AI agents for growing practices',
    features: [
      'Up to 8 client firms',
      '2,000 documents per month',
      'Ask LedgerPro AI agent',
      'Priority email support',
    ],
    cta: 'Start your free trial',
    highlighted: false,
  },
  {
    name: 'Professional',
    price: '7,499',
    period: '/month',
    tagline: 'For multi-client practices with API needs',
    features: [
      'Up to 15 client firms',
      'Unlimited documents',
      'AI agent + external API access',
      'E-way bill & import-export docs',
    ],
    cta: 'Start your free trial',
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: '18,999',
    period: '/month',
    tagline: 'Custom limits without schema changes',
    features: [
      'Unlimited client firms (or custom caps)',
      'Custom feature flags via config',
      'Dedicated account manager',
      'SLA & on-premise option',
    ],
    cta: 'Contact sales',
    highlighted: false,
  },
];

export default function LandingPricing() {
  return (
    <section id="pricing" className={SECTION_SHELL}>
      <SectionHeader
        eyebrow="Simple monthly rental"
        title="Pricing in Indian Rupees"
        description="Flexible monthly plans for CA firms and bookkeeping bureaus. Pay as you rent | no surprises."
      />

      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={staggerContainer}
        className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 lg:gap-8 max-w-6xl mx-auto"
      >
        {PRICING_PLANS.map((plan, i) => (
          <motion.div
            key={plan.name}
            variants={fadeUp}
            custom={i}
            {...hoverLift}
            className={`relative flex flex-col rounded-2xl border border-neutral-200 dark:border-neutral-800 p-8 text-left ${
              plan.highlighted ? 'pricing-card-popular md:scale-[1.02]' : 'premium-card bg-bg-primary'
            }`}
          >
            {plan.highlighted && (
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-medium uppercase tracking-wide px-3 py-1 rounded-full bg-accent text-accent-foreground">
                Most popular
              </span>
            )}
            <div className="text-sm font-medium text-text-secondary mb-1">{plan.name}</div>
            <div className="flex items-baseline gap-0.5 mb-2">
              <span className="text-lg font-medium text-text-secondary">₹</span>
              <span className="text-4xl font-semibold tracking-tight">{plan.price}</span>
              <span className="text-sm text-text-secondary ml-1">{plan.period}</span>
            </div>
            <p className="text-sm text-text-secondary mb-6">{plan.tagline}</p>
            <ul className="space-y-3 mb-8 flex-1">
              {plan.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-text-primary">
                  <Check className="w-4 h-4 mt-0.5 shrink-0 text-text-primary" strokeWidth={2} />
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/register"
              className={plan.highlighted ? 'btn-primary w-full text-center' : 'btn-secondary w-full text-center'}
            >
              {plan.cta}
            </Link>
          </motion.div>
        ))}
      </motion.div>

      <motion.p
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={fadeUp}
        className="text-center text-sm text-text-secondary mt-6"
      >
        All plans include 14-day free trial · No hidden fees
      </motion.p>
      <motion.p
        initial="hidden"
        whileInView="visible"
        viewport={viewportOnce}
        variants={fadeUp}
        className="text-center text-sm mt-3"
      >
        <a href="#" className="text-text-primary underline underline-offset-4 decoration-neutral-300 dark:decoration-neutral-700 hover:decoration-text-primary transition-colors">
          Ask about custom Enterprise pricing
        </a>
      </motion.p>
    </section>
  );
}

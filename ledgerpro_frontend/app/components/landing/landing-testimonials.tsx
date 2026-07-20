'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { SECTION_SHELL } from './landing-primitives';

// PLACEHOLDER testimonials — replace with verified client quotes before launch
const TESTIMONIALS = [
  {
    quote: 'Cut my weekly reconciliation time from 3 hours to 15 minutes.',
    author: 'Sharma & Associates',
    stat: '18 hrs/wk',
    statLabel: 'Saved on manual data entry',
  },
  {
    quote: 'We no longer worry about tax reconciliation errors. Auto-validation catches everything.',
    author: 'A.K. Mehta & Co.',
    stat: '0.0%',
    statLabel: 'GST mismatch rate achieved',
  },
  {
    quote: 'Processing import shipping papers used to take days. Now it is done in minutes.',
    author: 'Vanguard Shipping',
    stat: '14,000+',
    statLabel: 'Customs bills automated',
  },
  {
    quote: 'The processing speed and ERP sync has completely transformed our bookkeeping throughput.',
    author: 'Bookkeeping Daily',
    stat: '12 sec',
    statLabel: 'Average 500-invoice reconciliation',
  },
];

export default function LandingTestimonials() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  const next = useCallback(() => setActive((p) => (p + 1) % TESTIMONIALS.length), []);
  const prev = useCallback(() => setActive((p) => (p - 1 + TESTIMONIALS.length) % TESTIMONIALS.length), []);

  useEffect(() => {
    if (paused) return;
    const interval = setInterval(next, 4500);
    return () => clearInterval(interval);
  }, [paused, next]);

  const item = TESTIMONIALS[active];

  return (
    <section
      className={`${SECTION_SHELL} bg-neutral-50 dark:bg-neutral-950`}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="max-w-3xl mx-auto">
        <div className="premium-card p-8 md:p-10 relative overflow-hidden">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={active}
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -40 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
            >
              <blockquote className="text-xl md:text-2xl font-medium leading-relaxed text-text-primary mb-6">
                &ldquo;{item.quote}&rdquo;
              </blockquote>
              <p className="text-sm text-text-secondary mb-8">{item.author}</p>

              <div className="flex items-center gap-6 pt-6">
                <div>
                  <div className="text-2xl font-semibold tracking-tight text-text-primary">{item.stat}</div>
                  <div className="text-xs text-text-secondary mt-1 uppercase tracking-wide">{item.statLabel}</div>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>

          <div className="flex items-center justify-between mt-8">
            <div className="flex items-center gap-2">
              {TESTIMONIALS.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActive(i)}
                  className={`h-2 rounded-full transition-all ${
                    i === active ? 'w-6 bg-text-primary' : 'w-2 bg-neutral-300 dark:bg-neutral-700'
                  }`}
                  aria-label={`Go to testimonial ${i + 1}`}
                />
              ))}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={prev}
                className="p-2 rounded-lg border border-neutral-200 dark:border-neutral-800 hover:bg-bg-secondary transition-colors"
                aria-label="Previous testimonial"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={next}
                className="p-2 rounded-lg border border-neutral-200 dark:border-neutral-800 hover:bg-bg-secondary transition-colors"
                aria-label="Next testimonial"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

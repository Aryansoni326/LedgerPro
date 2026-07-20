'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

interface SolutionSectionProps {
  id?: string;
  eyebrow?: string;
  title: string;
  description: string;
  bullets?: string[];
  imagePosition?: 'left' | 'right';
  children?: React.ReactNode;
  className?: string;
}

export default function SolutionSection({
  id,
  eyebrow,
  title,
  description,
  bullets,
  imagePosition = 'left',
  children,
  className = '',
}: SolutionSectionProps) {
  const copy = (
    <motion.div
      initial={{ opacity: 0, x: imagePosition === 'left' ? 20 : -20 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="flex flex-col justify-center lg:px-2"
    >
      {eyebrow && <span className="text-sm font-medium text-text-secondary mb-2">{eyebrow}</span>}
      <h2 className="text-2xl sm:text-[1.75rem] font-semibold tracking-tight text-text-primary mb-3 leading-snug">
        {title}
      </h2>
      <p className="text-text-secondary text-[15px] leading-relaxed mb-5">{description}</p>
      {bullets && bullets.length > 0 && (
        <ul className="space-y-2.5">
          {bullets.map((item) => (
            <li key={item} className="flex items-start gap-2.5 text-sm text-text-primary leading-snug">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <Check className="h-3 w-3" strokeWidth={3} />
              </span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );

  const visualMotion = children ? (
    <motion.div
      initial={{ opacity: 0, x: imagePosition === 'left' ? -20 : 20 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="w-full"
    >
      {children}
    </motion.div>
  ) : null;

  return (
    <section id={id} className={`py-12 md:py-16 ${className}`}>
      <div className="max-w-6xl mx-auto px-5 sm:px-6">
        <div className="grid lg:grid-cols-2 gap-8 lg:gap-14 items-center">
          {imagePosition === 'left' ? (
            <>
              <div className="order-1">{visualMotion}</div>
              <div className="order-2">{copy}</div>
            </>
          ) : (
            <>
              <div className="order-2 lg:order-1">{copy}</div>
              <div className="order-1 lg:order-2">{visualMotion}</div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

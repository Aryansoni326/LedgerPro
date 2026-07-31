'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ChevronRight, type LucideIcon } from 'lucide-react';
import { fadeUp, hoverLift, viewportOnce } from './landing-motion';

export const SECTION_SHELL = 'landing-section landing-container';

interface SectionHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  className?: string;
}

export function SectionHeader({ eyebrow, title, description, className = '' }: SectionHeaderProps) {
  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={fadeUp}
      className={`text-center max-w-[65ch] mx-auto mb-8 md:mb-10 ${className}`}
    >
      <span className="badge-pill mb-4">{eyebrow}</span>
      <h2 className="text-3xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-text-primary mt-4 mb-4">
        {title}
      </h2>
      <p className="text-base md:text-lg text-text-secondary leading-relaxed max-w-[65ch] mx-auto">
        {description}
      </p>
    </motion.div>
  );
}

interface PremiumCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  footer?: string;
  className?: string;
  colSpan?: string;
}

export function PremiumCard({
  icon: Icon,
  title,
  description,
  footer,
  className = '',
  colSpan = '',
}: PremiumCardProps) {
  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={fadeUp}
      {...hoverLift}
      className={`${colSpan} group premium-card p-6 sm:p-7 flex flex-col hover:border-neutral-400 dark:hover:border-neutral-600 transition-colors duration-300 ${className}`}
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary mb-5 group-hover:scale-105 group-hover:border-neutral-400 dark:group-hover:border-neutral-600 transition-all duration-300">
        <Icon className="w-5 h-5 text-text-secondary group-hover:text-text-primary transition-colors" strokeWidth={1.75} />
      </span>
      <h3 className="text-lg font-semibold tracking-tight mb-2 text-text-primary">{title}</h3>
      <p className="text-text-secondary text-sm leading-relaxed flex-1 max-w-[65ch]">{description}</p>
      {footer && (
        <div className="mt-6 pt-5 flex items-center justify-between text-sm text-text-secondary group-hover:text-text-primary transition-colors">
          <span>{footer}</span>
          <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </div>
      )}
    </motion.div>
  );
}

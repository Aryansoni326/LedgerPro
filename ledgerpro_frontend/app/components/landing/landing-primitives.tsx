'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ChevronRight, type LucideIcon } from 'lucide-react';
import LandingPhoto, { ImageFrame } from './landing-photo';
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
      <h2 className="text-3xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-text-primary mt-4 mb-5">
        {title}
      </h2>
      <p className="text-lg md:text-xl text-text-secondary leading-relaxed max-w-[65ch] mx-auto">
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

interface SolutionRowProps {
  eyebrow?: string;
  title: string;
  description: string;
  bullets?: string[];
  imageSrc: string;
  imageAlt: string;
  imagePosition?: 'left' | 'right';
  layout?: 'split' | 'centered';
  index: number;
}

export function SolutionRow({
  eyebrow,
  title,
  description,
  bullets,
  imageSrc,
  imageAlt,
  imagePosition = 'left',
  layout = 'split',
  index,
}: SolutionRowProps) {
  if (layout === 'centered') {
    return (
      <motion.div
        {...hoverLift}
        className="flex flex-col items-center text-center py-10 md:py-12 border-b border-neutral-200/50 dark:border-neutral-800/50 last:border-0 w-full"
      >
        <div className="max-w-3xl mx-auto flex flex-col items-center mb-8 px-4">
          {eyebrow && <span className="badge-pill mb-4 w-fit">{eyebrow}</span>}
          <h3 className="text-3xl sm:text-4xl font-semibold tracking-tight text-text-primary mb-4 leading-tight">
            {title}
          </h3>
          <p className="text-text-secondary text-base sm:text-lg leading-relaxed max-w-[75ch] mb-8">
            {description}
          </p>
          {bullets && bullets.length > 0 && (
            <ul className="grid sm:grid-cols-3 gap-4 w-full max-w-4xl text-left mt-2">
              {bullets.map((item) => (
                <li
                  key={item}
                  className="flex items-center gap-3 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-bg-secondary/40 text-sm text-text-primary font-medium shadow-sm hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors"
                >
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-text-primary" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeUp}
          {...hoverLift}
          className="w-full max-w-5xl px-4"
        >
          <div className="relative aspect-[16/9] w-full rounded-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden bg-bg-secondary premium-card">
            <LandingPhoto src={imageSrc} alt={imageAlt} className="hover:scale-[1.01] transition-transform duration-500" />
            <div className="absolute inset-0 bg-gradient-to-t from-neutral-900/10 via-transparent to-transparent pointer-events-none dark:from-neutral-950/20" />
          </div>
        </motion.div>
      </motion.div>
    );
  }

  const visualBlock = (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={fadeUp}
      {...hoverLift}
      className="w-full mx-auto lg:mx-0"
    >
      <ImageFrame src={imageSrc} alt={imageAlt} gradient />
    </motion.div>
  );

  const copyBlock = (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      variants={fadeUp}
      custom={0.1}
      className="flex flex-col justify-center lg:px-4 max-w-[65ch]"
    >
      {eyebrow && <span className="badge-pill mb-4 w-fit">{eyebrow}</span>}
      <h3 className="text-2xl sm:text-3xl font-semibold tracking-tight text-text-primary mb-4 leading-snug">
        {title}
      </h3>
      <p className="text-text-secondary text-base leading-relaxed mb-6">{description}</p>
      {bullets && bullets.length > 0 && (
        <ul className="space-y-3">
          {bullets.map((item) => (
            <li key={item} className="flex items-start gap-3 text-sm text-text-primary">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-text-primary" />
              {item}
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );

  return (
    <motion.div
      {...hoverLift}
      className={`grid lg:grid-cols-2 gap-8 lg:gap-12 items-center py-8 md:py-10`}
    >
      {imagePosition === 'left' ? (
        <>
          <div className="order-1 flex items-center">{visualBlock}</div>
          <div className="order-2 flex items-center">{copyBlock}</div>
        </>
      ) : (
        <>
          <div className="order-2 lg:order-1 flex items-center">{copyBlock}</div>
          <div className="order-1 lg:order-2 flex items-center">{visualBlock}</div>
        </>
      )}
    </motion.div>
  );
}

'use client';

import React from 'react';
import { LANDING_IMAGE_VERSION } from './landing-photos';

export const PHOTO_ASPECT = 'aspect-[4/3]';

interface LandingPhotoProps {
  src: string;
  alt: string;
  className?: string;
}

export default function LandingPhoto({ src, alt, className = '' }: LandingPhotoProps) {
  const versioned = `${src}?v=${LANDING_IMAGE_VERSION}`;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={versioned}
      alt={alt}
      className={`w-full h-full object-contain object-center p-3 dark:invert dark:hue-rotate-180 ${className}`}
      loading="lazy"
      decoding="async"
    />
  );
}

interface ImageFrameProps {
  src: string;
  alt: string;
  className?: string;
  gradient?: boolean;
  children?: React.ReactNode;
}

export function ImageFrame({ src, alt, className = '', gradient = false, children }: ImageFrameProps) {
  return (
    <div
      className={`relative ${PHOTO_ASPECT} w-full rounded-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden bg-bg-secondary premium-card ${className}`}
    >
      <LandingPhoto src={src} alt={alt} />
      {gradient && (
        <div className="absolute inset-0 bg-gradient-to-t from-neutral-900/20 via-transparent to-transparent pointer-events-none dark:from-neutral-950/35" />
      )}
      {children}
    </div>
  );
}

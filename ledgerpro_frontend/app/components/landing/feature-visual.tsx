'use client';

import React from 'react';
import { FeatureSymbolBanner, type FeatureSymbolKey } from './feature-symbols';

/** Uniform strip height when showing symbol-only visuals */
export const CARD_IMAGE_HEIGHT = 'h-[180px] sm:h-[200px]';

interface FeatureVisualProps {
  symbol?: FeatureSymbolKey;
  children?: React.ReactNode;
  compact?: boolean;
}

/** Product mock card — optional symbol header, no stock photos. */
export default function FeatureVisual({ symbol, children, compact = true }: FeatureVisualProps) {
  return (
    <div className="rounded-xl border border-border-subtle bg-bg-primary shadow-lg overflow-hidden ring-1 ring-text-primary/[0.05] max-w-lg w-full mx-auto lg:mx-0">
      {symbol && !children && (
        <div className={`relative w-full ${CARD_IMAGE_HEIGHT} bg-bg-secondary overflow-hidden`}>
          <FeatureSymbolBanner symbol={symbol} className="absolute inset-0" />
        </div>
      )}
      {children && (
        <div className={symbol ? `bg-bg-primary ${compact ? 'p-3 sm:p-4' : 'p-4 sm:p-5'}` : compact ? 'p-3 sm:p-4' : 'p-4 sm:p-5'}>
          {children}
        </div>
      )}
    </div>
  );
}

export function ImageVisual({ symbol }: { symbol: FeatureSymbolKey }) {
  return <FeatureVisual symbol={symbol} />;
}

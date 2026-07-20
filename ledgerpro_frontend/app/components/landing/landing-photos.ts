/** Landing photos — unique file per slot, 900×500 crop, no text overlays */
export const LANDING_IMAGE_VERSION = '4';

export const LANDING_PHOTOS = {
  solutions: {
    multiFirm: '/images/landing/sol-multi-firm.jpg',
    invoices: '/images/landing/sol-invoices.jpg',
    gst: '/images/landing/sol-gst.jpg',
    analytics: '/images/landing/sol-analytics.jpg',
    extract: '/images/landing/sol-extract.jpg',
    verify: '/images/landing/sol-verify.jpg',
  },
  steps: {
    upload: '/images/landing/step-upload.jpg',
    ai: '/images/landing/step-ai.jpg',
    export: '/images/landing/step-export.jpg',
  },
  features: {
    llm: '/images/landing/feat-llm.jpg',
    gst: '/images/landing/feat-gst.jpg',
    trade: '/images/landing/feat-trade.jpg',
    eway: '/images/landing/feat-eway.jpg',
    analytics: '/images/landing/feat-analytics.jpg',
  },
} as const;

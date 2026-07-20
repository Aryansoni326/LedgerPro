'use client';

import React from 'react';
import LandingHeader from '../components/landing/landing-header';
import LandingPricing from '../components/landing/landing-pricing';
import SaasFooter from '../components/saas-footer';

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary transition-colors duration-300 overflow-x-hidden font-sans relative">
      <div className="fixed inset-0 landing-gradient-mesh pointer-events-none z-0" aria-hidden />
      <LandingHeader />
      
      {/* Container with top padding to prevent header overlap */}
      <main className="relative z-10 pt-20">
        <LandingPricing />
      </main>

      <SaasFooter variant="full" />
    </div>
  );
}

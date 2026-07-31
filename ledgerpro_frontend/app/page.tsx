'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from './auth-context';
import LandingHeader from './components/landing/landing-header';
import LandingHero from './components/landing/landing-hero';
import LandingProblem from './components/landing/landing-problem';
import LandingSolutions from './components/landing/landing-solutions';
import LandingTestimonials from './components/landing/landing-testimonials';
import LandingHowItWorks from './components/landing/landing-how-it-works';
import LandingFeatures from './components/landing/landing-features';
import LandingCta from './components/landing/landing-cta';
import SaasFooter from './components/saas-footer';

export default function Home() {
  const { token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && token) {
      router.replace('/dashboard');
    }
  }, [token, loading, router]);

  if (loading || token) {
    return null;
  }
  return (
    <div
      id="top"
      className="min-h-screen bg-bg-primary text-text-primary transition-colors duration-300 overflow-x-hidden font-sans relative"
    >
      <div className="fixed inset-0 landing-gradient-mesh pointer-events-none z-0" aria-hidden />

      <LandingHeader />
      <LandingHero />
      <LandingProblem />
      <LandingHowItWorks />
      <LandingSolutions />
      <LandingFeatures />
      <LandingTestimonials />
      <LandingCta />
      <SaasFooter variant="full" />
    </div>
  );
}

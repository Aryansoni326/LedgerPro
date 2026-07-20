'use client';

import React, { useEffect } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from './auth-context';
import LandingHeader from './components/landing/landing-header';
import LandingHero from './components/landing/landing-hero';
import LandingSolutions from './components/landing/landing-solutions';
import LandingTestimonials from './components/landing/landing-testimonials';
import LandingHowItWorks from './components/landing/landing-how-it-works';
import LandingFeatures from './components/landing/landing-features';
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
    <div className="min-h-screen bg-bg-primary text-text-primary transition-colors duration-300 overflow-x-hidden font-sans relative">
      <div className="fixed inset-0 landing-gradient-mesh pointer-events-none z-0" aria-hidden />
      <motion.div
        className="fixed top-20 left-[10%] w-72 h-72 rounded-full bg-neutral-900/[0.03] dark:bg-neutral-100/[0.03] blur-3xl pointer-events-none z-0"
        animate={{ y: [0, -20, 0], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        aria-hidden
      />
      <motion.div
        className="fixed top-40 right-[5%] w-96 h-96 rounded-full bg-neutral-900/[0.02] dark:bg-neutral-100/[0.02] blur-3xl pointer-events-none z-0"
        animate={{ y: [0, 16, 0], opacity: [0.3, 0.6, 0.3] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        aria-hidden
      />

      <LandingHeader />
      <LandingHero />
      <LandingSolutions />
      <LandingTestimonials />
      <LandingHowItWorks />
      <LandingFeatures />
      <SaasFooter variant="full" />
    </div>
  );
}

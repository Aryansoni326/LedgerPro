'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Moon, Sun, Menu, X } from 'lucide-react';
import { useTheme } from '../../providers';
import { useAuth } from '../../auth-context';
import LedgerProLogo from '../ledgerpro-logo';

const NAV_LINKS = [
  { href: '/#solutions', label: 'Solutions' },
  { href: '/#features', label: 'Features' },
  { href: '/#how-it-works', label: 'How it Works' },
  { href: '/pricing', label: 'Pricing' },
];

export default function LandingHeader() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 w-full z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-bg-primary/80 backdrop-blur-xl shadow-[0_4px_24px_rgb(0,0,0,0.04)] dark:shadow-[0_4px_24px_rgb(0,0,0,0.25)]'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <LedgerProLogo size="md" href="/" />
          <nav className="hidden md:flex items-center gap-6 text-sm text-text-secondary">
            {NAV_LINKS.map((link) => (
              <a key={link.href} href={link.href} className="hover:text-text-primary transition-colors">
                {link.label}
              </a>
            ))}
          </nav>
        </div>

        <div className="hidden md:flex items-center gap-4">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg border border-neutral-200 dark:border-neutral-800 hover:bg-bg-secondary hover:shadow-[0_0_20px_var(--brand-glow)] transition-all"
            aria-label="Toggle theme"
          >
            {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
          {isAuthenticated ? (
            <Link href="/dashboard" className="btn-secondary text-sm px-4 py-2">
              Dashboard
            </Link>
          ) : (
            <>
              <Link href="/owner/login" className="text-sm text-text-secondary hover:text-text-primary transition-colors">
                Owners Login
              </Link>
              <Link href="/login" className="text-sm text-text-secondary hover:text-text-primary transition-colors">
                Login
              </Link>
              <Link href="/register" className="btn-primary text-sm px-4 py-2">
                Get Started
              </Link>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 md:hidden">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg border border-neutral-200 dark:border-neutral-800 hover:shadow-[0_0_20px_var(--brand-glow)] transition-all"
            aria-label="Toggle theme"
          >
            {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg border border-neutral-200 dark:border-neutral-800"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, x: '100%' }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: '100%' }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="fixed inset-0 top-16 bg-bg-primary/95 backdrop-blur-xl md:hidden z-40"
          >
            <div className="px-6 py-8 space-y-5">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="block text-lg text-text-primary"
                >
                  {link.label}
                </a>
              ))}
              <div className="h-4" aria-hidden />
              {isAuthenticated ? (
                <Link
                  href="/dashboard"
                  onClick={() => setMobileMenuOpen(false)}
                  className="block w-full text-center btn-secondary py-3"
                >
                  Dashboard
                </Link>
              ) : (
                <div className="flex flex-col gap-3">
                  <Link href="/owner/login" onClick={() => setMobileMenuOpen(false)} className="text-center py-2 text-text-secondary">
                    Owners Login
                  </Link>
                  <Link href="/login" onClick={() => setMobileMenuOpen(false)} className="text-center py-2 text-text-secondary">
                    Login
                  </Link>
                  <Link href="/register" onClick={() => setMobileMenuOpen(false)} className="btn-primary text-center py-3">
                    Get Started
                  </Link>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

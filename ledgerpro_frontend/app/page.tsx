'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { useTheme } from './providers';
import { useAuth } from './auth-context';
import { 
  ArrowRight, 
  UploadCloud, 
  Cpu, 
  CheckCircle2, 
  FileSpreadsheet, 
  Globe, 
  FileCheck, 
  ChevronRight,
  Sparkles,
  BarChart3,
  Moon,
  Sun,
  Menu,
  X
} from 'lucide-react';
import SaasFooter from './components/saas-footer';

const CREDIBILITY_QUOTES = [
  {
    stat: "18 hrs/wk",
    label: "Saved on manual data entry",
    quote: "\"LedgerPro eliminated our data entry backlog in under a week. The accuracy is unmatched.\"",
    author: "Apex Ledger Group"
  },
  {
    stat: "0.0%",
    label: "GST mismatch rate achieved",
    quote: "\"We no longer worry about tax reconciliation errors. The auto-validation catches everything.\"",
    author: "A.K. Mehta & Co."
  },
  {
    stat: "14,000+",
    label: "Customs bills automated",
    quote: "\"Processing import shipping papers used to take days. Now it is done in minutes.\"",
    author: "Vanguard Shipping"
  },
  {
    stat: "12 sec",
    label: "Average 500-invoice reconciliation time",
    quote: "\"The processing speed and ERP sync has completely transformed our bookkeeping throughput.\"",
    author: "Bookkeeping Daily"
  }
];

export default function Home() {
  const { theme, toggleTheme, mounted } = useTheme();
  const { isAuthenticated } = useAuth();
  const [activeQuote, setActiveQuote] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Auto-rotate quotes
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveQuote((prev) => (prev + 1) % CREDIBILITY_QUOTES.length);
    }, 4500);
    return () => clearInterval(interval);
  }, []);

  if (!mounted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-primary text-text-primary">
        <div className="text-sm font-mono animate-pulse">Loading LedgerPro...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary transition-colors duration-200 selection:bg-text-primary selection:text-bg-primary overflow-x-hidden font-sans">
      
      {/* 1. Header Navigation */}
      <header className="fixed top-0 left-0 w-full bg-bg-primary/80 backdrop-blur-md z-50 border-b border-border-subtle transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="text-lg font-bold tracking-tight flex items-center gap-2">
              LedgerPro
              <span className="text-[10px] font-mono font-normal px-1 py-0.25 border border-border-subtle rounded bg-bg-secondary">
                v2.0
              </span>
            </Link>
            
            <nav className="hidden md:flex items-center gap-6 text-sm text-text-secondary">
              <a href="#features" className="hover:text-text-primary transition-colors">Features</a>
              <a href="#how-it-works" className="hover:text-text-primary transition-colors">How it Works</a>
              <a href="#pricing" className="hover:text-text-primary transition-colors">Pricing</a>
            </nav>
          </div>

          <div className="hidden md:flex items-center gap-4">
            <button
              onClick={toggleTheme}
              className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
              aria-label="Toggle Theme"
            >
              {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            </button>
            
            {isAuthenticated ? (
              <Link 
                href="/dashboard"
                className="text-sm font-semibold px-4 py-2 border border-border-subtle rounded hover:bg-bg-secondary transition-all"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link 
                  href="/login" 
                  className="text-sm font-semibold px-3 py-2 text-text-secondary hover:text-text-primary transition-colors"
                >
                  Login
                </Link>
                <Link 
                  href="/login"
                  className="text-sm font-semibold px-4 py-2 bg-accent text-accent-foreground rounded hover:opacity-90 transition-all"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center gap-3 md:hidden">
            <button
              onClick={toggleTheme}
              className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
            >
              {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
            >
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="absolute top-16 left-0 w-full bg-bg-primary border-b border-border-subtle px-6 py-6 space-y-4 md:hidden flex flex-col transition-colors duration-200"
            >
              <a 
                href="#features" 
                onClick={() => setMobileMenuOpen(false)}
                className="text-sm text-text-secondary hover:text-text-primary"
              >
                Features
              </a>
              <a 
                href="#how-it-works" 
                onClick={() => setMobileMenuOpen(false)}
                className="text-sm text-text-secondary hover:text-text-primary"
              >
                How it Works
              </a>
              <a 
                href="#pricing" 
                onClick={() => setMobileMenuOpen(false)}
                className="text-sm text-text-secondary hover:text-text-primary"
              >
                Pricing
              </a>
              <hr className="border-border-subtle" />
              {isAuthenticated ? (
                <Link 
                  href="/dashboard"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full text-center py-2.5 border border-border-subtle rounded text-sm font-semibold hover:bg-bg-secondary"
                >
                  Dashboard
                </Link>
              ) : (
                <div className="flex flex-col gap-3">
                  <Link 
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full text-center py-2 text-sm text-text-secondary hover:text-text-primary"
                  >
                    Login
                  </Link>
                  <Link 
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full text-center py-2.5 bg-accent text-accent-foreground rounded text-sm font-semibold hover:opacity-90"
                  >
                    Get Started
                  </Link>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* 2. Hero Section */}
      <section className="pt-32 pb-20 md:pt-40 md:pb-28 max-w-7xl mx-auto px-6 flex flex-col items-center text-center">
        {/* Tagline Badge */}
        <motion.div 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 border border-border-subtle px-3 py-1 rounded-full text-xs font-mono text-text-secondary mb-6 bg-bg-secondary/50"
        >
          <Sparkles className="w-3.5 h-3.5" />
          AI-Powered Ledger Automation
        </motion.div>

        {/* Headline */}
        <motion.h1 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight max-w-3xl leading-[1.1] mb-6 text-text-primary"
        >
          Automate your invoices, reconciliations, and GST.
        </motion.h1>

        {/* Subheadline */}
        <motion.p 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="text-text-secondary text-base sm:text-lg md:text-xl max-w-xl mb-10 leading-relaxed"
        >
          The zero-overhead ledger processor built specifically for accountants. Automatically extract data, audit tax filings, and sync with your ERP.
        </motion.p>

        {/* Hero CTAs */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="flex flex-col sm:flex-row gap-4 items-center mb-16"
        >
          <Link
            href="/login"
            className="w-full sm:w-auto px-8 py-4 bg-accent text-accent-foreground hover:opacity-90 font-semibold rounded-md flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
          >
            Get Started <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/login"
            className="w-full sm:w-auto px-8 py-4 border border-border-subtle bg-bg-primary hover:bg-bg-secondary font-semibold rounded-md flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
          >
            Book a Demo
          </Link>
        </motion.div>

        {/* Visual Line Decor */}
        <div className="w-full h-px bg-gradient-to-r from-transparent via-border-subtle to-transparent max-w-5xl"></div>
      </section>

      {/* 3. Credibility Testimonials / Stats Carousel */}
      <section className="py-12 bg-bg-secondary/40 border-y border-border-subtle transition-colors duration-200">
        <div className="max-w-4xl mx-auto px-6 h-40 md:h-32 flex flex-col justify-center overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeQuote}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.4 }}
              className="grid md:grid-cols-3 items-center gap-6"
            >
              <div className="md:col-span-1 text-center md:text-left border-b md:border-b-0 md:border-r border-border-subtle pb-2 md:pb-0 md:pr-6">
                <div className="text-3xl font-extrabold tracking-tight font-mono text-text-primary">
                  {CREDIBILITY_QUOTES[activeQuote].stat}
                </div>
                <div className="text-xs font-mono text-text-secondary mt-1">
                  {CREDIBILITY_QUOTES[activeQuote].label}
                </div>
              </div>
              <div className="md:col-span-2 text-center md:text-left">
                <p className="text-sm md:text-base italic text-text-primary font-mono leading-relaxed">
                  {CREDIBILITY_QUOTES[activeQuote].quote}
                </p>
                <div className="text-xs text-text-secondary mt-2 font-semibold">
                  — {CREDIBILITY_QUOTES[activeQuote].author}
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </section>

      {/* 4. "How It Works" Section */}
      <section id="how-it-works" className="py-20 md:py-28 max-w-7xl mx-auto px-6 border-b border-border-subtle">
        <div className="text-center max-w-2xl mx-auto mb-16 space-y-4">
          <span className="text-xs font-mono border border-border-subtle px-3 py-1 rounded-full uppercase tracking-wider text-text-secondary bg-bg-secondary">
            Process Overview
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">How it works</h2>
          <p className="text-text-secondary">Three simple phases to completely automate accounting entry bottlenecks.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 relative">
          {/* Card 1 */}
          <div className="p-8 border border-border-subtle rounded-lg bg-bg-secondary hover:border-text-primary/40 transition-all duration-300 group">
            <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center text-sm font-mono font-bold mb-6 bg-bg-primary group-hover:bg-text-primary group-hover:text-bg-primary transition-all duration-300">
              01
            </div>
            <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
              <UploadCloud className="w-4.5 h-4.5" /> Upload Invoices
            </h3>
            <p className="text-text-secondary text-sm leading-relaxed">
              Drag-and-drop folders, upload scans, or forward billing emails. Supports PDFs, images, and customs shipping documents.
            </p>
          </div>

          {/* Card 2 */}
          <div className="p-8 border border-border-subtle rounded-lg bg-bg-secondary hover:border-text-primary/40 transition-all duration-300 group">
            <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center text-sm font-mono font-bold mb-6 bg-bg-primary group-hover:bg-text-primary group-hover:text-bg-primary transition-all duration-300">
              02
            </div>
            <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
              <Cpu className="w-4.5 h-4.5" /> AI Processing
            </h3>
            <p className="text-text-secondary text-sm leading-relaxed">
              Our specialized LLM extracts metadata, matches items, and cross-references active GST registration databases for compliance.
            </p>
          </div>

          {/* Card 3 */}
          <div className="p-8 border border-border-subtle rounded-lg bg-bg-secondary hover:border-text-primary/40 transition-all duration-300 group">
            <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center text-sm font-mono font-bold mb-6 bg-bg-primary group-hover:bg-text-primary group-hover:text-bg-primary transition-all duration-300">
              03
            </div>
            <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
              <FileSpreadsheet className="w-4.5 h-4.5" /> Sync & Export
            </h3>
            <p className="text-text-secondary text-sm leading-relaxed">
              Directly export reconciled transactions to Tally, SAP, or QuickBooks, and download compliant GSTR return files in one click.
            </p>
          </div>
        </div>
      </section>

      {/* 5. Feature Bento Grid */}
      <section id="features" className="py-20 md:py-28 max-w-7xl mx-auto px-6 border-b border-border-subtle">
        <div className="text-center max-w-2xl mx-auto mb-16 space-y-4">
          <span className="text-xs font-mono border border-border-subtle px-3 py-1 rounded-full uppercase tracking-wider text-text-secondary bg-bg-secondary">
            Capabilities
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Structured for high accuracy</h2>
          <p className="text-text-secondary">Robust utilities built to tackle complex corporate invoicing and tax auditing.</p>
        </div>

        {/* Bento Grid */}
        <div className="grid md:grid-cols-6 gap-6">
          
          {/* Card 1: Invoice Extraction (Span 4) */}
          <div className="md:col-span-4 p-8 border border-border-subtle rounded-lg bg-bg-secondary flex flex-col justify-between hover:border-text-primary/40 transition-colors group">
            <div>
              <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center bg-bg-primary mb-6 text-text-primary">
                <Cpu className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold mb-3">LLM Invoice Extraction</h3>
              <p className="text-text-secondary text-sm leading-relaxed max-w-lg">
                Engineered parser capable of reading structured tables, handwritten bills, and multi-currency values. Automatically maps raw rows to corresponding inventory SKUs with zero templates needed.
              </p>
            </div>
            <div className="mt-8 pt-6 border-t border-border-subtle flex items-center justify-between text-xs font-mono text-text-secondary group-hover:text-text-primary transition-colors">
              <span>99.8% Extraction Accuracy</span>
              <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Card 2: GST Validation (Span 2) */}
          <div className="md:col-span-2 p-8 border border-border-subtle rounded-lg bg-bg-secondary flex flex-col justify-between hover:border-text-primary/40 transition-colors group">
            <div>
              <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center bg-bg-primary mb-6 text-text-primary">
                <FileCheck className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold mb-3">GST Verification</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Queries government databases in real-time to validate vendor GSTIN active status, tax slab rules, and match claims.
              </p>
            </div>
            <div className="mt-8 pt-6 border-t border-border-subtle flex items-center justify-between text-xs font-mono text-text-secondary group-hover:text-text-primary transition-colors">
              <span>Tax Reconciliation</span>
              <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Card 3: Import-Export Tracking (Span 2) */}
          <div className="md:col-span-2 p-8 border border-border-subtle rounded-lg bg-bg-secondary flex flex-col justify-between hover:border-text-primary/40 transition-colors group">
            <div>
              <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center bg-bg-primary mb-6 text-text-primary">
                <Globe className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold mb-3">Import-Export tracking</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Import bills of entry and shipping details are automatically matched to verify tax rates and logistics data.
              </p>
            </div>
            <div className="mt-8 pt-6 border-t border-border-subtle flex items-center justify-between text-xs font-mono text-text-secondary group-hover:text-text-primary transition-colors">
              <span>Cross-border Invoicing</span>
              <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Card 4: E-Way Bill Management (Span 2) */}
          <div className="md:col-span-2 p-8 border border-border-subtle rounded-lg bg-bg-secondary flex flex-col justify-between hover:border-text-primary/40 transition-colors group">
            <div>
              <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center bg-bg-primary mb-6 text-text-primary">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold mb-3">E-Way Bills</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Verify transport pin-code distances, generate vehicle details, and auto-submit transport registry files in seconds.
              </p>
            </div>
            <div className="mt-8 pt-6 border-t border-border-subtle flex items-center justify-between text-xs font-mono text-text-secondary group-hover:text-text-primary transition-colors">
              <span>Compliance Check</span>
              <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Card 5: Turnover Analytics (Span 2) */}
          <div className="md:col-span-2 p-8 border border-border-subtle rounded-lg bg-bg-secondary flex flex-col justify-between hover:border-text-primary/40 transition-colors group">
            <div>
              <div className="w-10 h-10 border border-border-subtle rounded flex items-center justify-center bg-bg-primary mb-6 text-text-primary">
                <BarChart3 className="w-5 h-5" />
              </div>
              <h3 className="text-xl font-bold mb-3">Turnover Analytics</h3>
              <p className="text-text-secondary text-sm leading-relaxed">
                Access instant cashflow analysis, tax projections, and detect billing anomalies before filing returns.
              </p>
            </div>
            <div className="mt-8 pt-6 border-t border-border-subtle flex items-center justify-between text-xs font-mono text-text-secondary group-hover:text-text-primary transition-colors">
              <span>Real-Time Reports</span>
              <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

        </div>
      </section>

      {/* 6. Pricing Placeholder Block (to satisfy links) */}
      <section id="pricing" className="py-20 md:py-28 max-w-7xl mx-auto px-6 text-center border-b border-border-subtle">
        <div className="max-w-2xl mx-auto space-y-4 mb-10">
          <span className="text-xs font-mono border border-border-subtle px-3 py-1 rounded-full uppercase tracking-wider text-text-secondary bg-bg-secondary">
            Enterprise Ready
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Flexible, transparent pricing</h2>
          <p className="text-text-secondary">Start free during development. Upgrade for bulk volume API access and customized audit routing.</p>
        </div>
        
        <div className="inline-flex flex-col border border-border-subtle rounded-lg bg-bg-secondary p-8 max-w-sm text-left">
          <div className="text-sm font-mono text-text-secondary mb-1">Developer Core</div>
          <div className="text-4xl font-extrabold mb-3">$0<span className="text-sm font-normal text-text-secondary font-mono">/mo</span></div>
          <p className="text-xs text-text-secondary mb-6 leading-relaxed">Perfect for setting up ledger infrastructure and validating local files.</p>
          <Link href="/login" className="w-full text-center py-2.5 bg-accent text-accent-foreground font-semibold rounded text-sm hover:opacity-90 active:scale-98 transition-all">
            Get Started Free
          </Link>
        </div>
      </section>

      <SaasFooter variant="full" />

    </div>
  );
}

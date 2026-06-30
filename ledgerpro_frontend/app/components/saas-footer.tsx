'use client';

import React from 'react';
import Link from 'next/link';

interface SaasFooterProps {
  variant?: 'full' | 'minimal';
}

export default function SaasFooter({ variant = 'full' }: SaasFooterProps) {
  if (variant === 'minimal') {
    return (
      <footer className="border-t border-border-subtle bg-bg-primary text-text-secondary transition-colors duration-200 mt-auto">
        <div className="max-w-5xl mx-auto px-4 md:px-8 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-[10px] font-mono">
          <div className="flex items-center gap-3">
            <Link href="/" className="font-bold text-text-primary hover:opacity-80 transition-opacity">
              LedgerPro
            </Link>
            <span className="hidden sm:inline text-border-subtle">·</span>
            <span className="hidden sm:inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              Operational
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/#features" className="hover:text-text-primary transition-colors">
              Features
            </Link>
            <Link href="/#pricing" className="hover:text-text-primary transition-colors">
              Pricing
            </Link>
            <a href="#" className="hover:text-text-primary transition-colors">
              Privacy
            </a>
            <span>&copy; {new Date().getFullYear()} LedgerPro</span>
          </div>
        </div>
      </footer>
    );
  }

  return (
    <footer className="bg-bg-primary text-text-primary pt-20 pb-12 border-t border-border-subtle transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-5 gap-8 mb-16">
        <div className="col-span-2 space-y-4">
          <Link href="/" className="text-lg font-bold tracking-tight">
            LedgerPro
          </Link>
          <p className="text-xs text-text-secondary max-w-xs leading-relaxed font-mono">
            AI-driven invoice and GST automation engineered specifically for corporate accountants and bookkeeping bureaus.
          </p>
          <div className="inline-flex items-center gap-2 border border-border-subtle rounded-full px-2.5 py-1 text-[10px] font-mono text-text-secondary bg-bg-secondary">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            All Systems Operational
          </div>
        </div>

        <div className="space-y-4">
          <h4 className="text-xs font-mono uppercase tracking-wider text-text-primary font-bold">Product</h4>
          <ul className="space-y-2 text-xs text-text-secondary font-mono">
            <li><a href="#features" className="hover:text-text-primary transition-colors">Features</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Security</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">API Reference</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Integrations</a></li>
          </ul>
        </div>

        <div className="space-y-4">
          <h4 className="text-xs font-mono uppercase tracking-wider text-text-primary font-bold">Company</h4>
          <ul className="space-y-2 text-xs text-text-secondary font-mono">
            <li><a href="#" className="hover:text-text-primary transition-colors">About Us</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Careers</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Press Kit</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Contact</a></li>
          </ul>
        </div>

        <div className="space-y-4">
          <h4 className="text-xs font-mono uppercase tracking-wider text-text-primary font-bold">Legal</h4>
          <ul className="space-y-2 text-xs text-text-secondary font-mono">
            <li><a href="#" className="hover:text-text-primary transition-colors">Privacy Policy</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Terms of Service</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">GST Compliance</a></li>
            <li><a href="#" className="hover:text-text-primary transition-colors">Trust Center</a></li>
          </ul>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pt-8 border-t border-border-subtle flex flex-col md:flex-row items-center justify-between gap-4 text-xs font-mono text-text-secondary">
        <div>&copy; {new Date().getFullYear()} LedgerPro Inc. All rights reserved.</div>
        <div className="flex gap-4">
          <a href="#" className="hover:text-text-primary transition-colors">Twitter</a>
          <a href="#" className="hover:text-text-primary transition-colors">GitHub</a>
          <a href="#" className="hover:text-text-primary transition-colors">LinkedIn</a>
        </div>
      </div>
    </footer>
  );
}

'use client';

import React from 'react';
import {
  LayoutDashboard,
  FileText,
  Globe,
  Truck,
  Database,
  Check,
  Upload,
  Sparkles,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import LedgerProLogo from '../ledgerpro-logo';

/** Premium dashboard preview for landing page */
export function DashboardShowcase({ compact = false }: { compact?: boolean }) {
  const bars = [42, 58, 51, 74, 68, 92, 85, 78];
  return (
    <div
      className={`rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-gradient-to-br from-bg-primary via-bg-primary to-bg-secondary overflow-hidden text-left premium-card ${
        compact ? 'max-h-[280px] sm:max-h-none' : ''
      }`}
    >
      <div className="flex items-center gap-2 px-4 py-2.5 bg-bg-secondary/80">
        <div className="flex gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-neutral-400/80" />
          <span className="w-2.5 h-2.5 rounded-full bg-neutral-500/80" />
          <span className="w-2.5 h-2.5 rounded-full bg-neutral-600/80" />
        </div>
        <span className="text-[10px] text-text-secondary ml-2">app.ledgerpro.in/dashboard</span>
      </div>

      <div className={`flex ${compact ? 'min-h-[260px]' : 'min-h-[440px]'}`}>
        <aside className="hidden sm:flex w-48 shrink-0 border-r border-neutral-200 dark:border-neutral-800 bg-bg-secondary/60 flex-col p-4">
          <div className="mb-5 scale-90 origin-left">
            <LedgerProLogo size="sm" href={undefined} />
          </div>
          <nav className="space-y-1 text-xs">
            {[
              { icon: LayoutDashboard, label: 'Overview', active: true },
              { icon: FileText, label: 'Invoices' },
              { icon: Globe, label: 'Import-Export' },
              { icon: Truck, label: 'E-way Bills' },
              { icon: Database, label: 'Cloud Vault' },
            ].map(({ icon: Icon, label, active }) => (
              <div
                key={label}
                className={`flex items-center gap-2 px-2.5 py-2 rounded-lg transition-colors ${
                  active
                    ? 'bg-accent text-accent-foreground font-medium shadow-sm'
                    : 'text-text-secondary hover:bg-bg-primary/50'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </div>
            ))}
          </nav>
        </aside>

        <div className="flex-1 min-w-0 bg-bg-primary">
          <div className="flex items-center justify-between gap-2 px-4 py-3 bg-bg-secondary/30">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-text-secondary hidden md:inline">Workspace</span>
              <span className="px-2.5 py-1 rounded-md border border-border-subtle bg-bg-secondary font-medium shadow-sm">
                Sharma & Associates
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-text-secondary">
                <span className="w-1.5 h-1.5 rounded-full bg-text-primary animate-pulse" />
                Live
              </span>
              <div className="w-7 h-7 rounded-full bg-accent text-accent-foreground flex items-center justify-center text-[10px] font-bold">
                A
              </div>
            </div>
          </div>

          <div className={`p-4 space-y-4 ${compact ? 'overflow-hidden' : ''}`}>
            <div className={`flex flex-wrap items-end justify-between gap-2 ${compact ? 'hidden' : ''}`}>
              <div>
                <h3 className="text-lg font-semibold">Overview</h3>
                <p className="text-[11px] text-text-secondary">Verified analytics · Q1 2026</p>
              </div>
              <div className="flex gap-1 text-[10px]">
                {['Month', 'Quarter', 'Year'].map((r, i) => (
                  <span
                    key={r}
                    className={`px-2 py-1 rounded ${i === 0 ? 'bg-accent text-accent-foreground' : 'text-text-secondary border border-border-subtle'}`}
                  >
                    {r}
                  </span>
                ))}
              </div>
            </div>

            <div className={`grid grid-cols-2 gap-2 ${compact ? 'lg:grid-cols-2' : 'lg:grid-cols-4'}`}>
              {[
                { label: 'Purchase bills', value: '248', sub: '+12% vs last month', up: true },
                { label: 'Sales bills', value: '186', sub: '+8% vs last month', up: true },
                { label: 'GST verified', value: '99.8%', sub: 'Match rate', up: true },
                { label: 'Pending review', value: '12', sub: 'Needs action', up: false },
              ].map((c) => (
                <div
                  key={c.label}
                  className="p-3 rounded-xl border border-border-subtle bg-gradient-to-b from-bg-secondary to-bg-primary shadow-sm"
                >
                  <div className="text-[10px] text-text-secondary">{c.label}</div>
                  <div className="text-xl font-semibold mt-1 tabular-nums">{c.value}</div>
                  <div className={`text-[10px] mt-0.5 flex items-center gap-1 ${c.up ? 'text-text-secondary' : 'text-text-secondary'}`}>
                    {c.up ? <TrendingUp className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                    {c.sub}
                  </div>
                </div>
              ))}
            </div>

            <div className={`grid gap-3 ${compact ? 'hidden md:grid md:grid-cols-5' : 'md:grid-cols-5'}`}>
              <div className="md:col-span-3 rounded-xl border border-border-subtle p-4 bg-bg-secondary/50">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-xs font-medium">Turnover trend</span>
                  <span className="text-[10px] text-text-secondary">₹ in lakhs</span>
                </div>
                <div className="flex items-end gap-1.5 h-28">
                  {bars.map((h, i) => (
                    <div key={i} className="flex-1 flex flex-col justify-end h-full">
                      <div
                        className="w-full rounded-t-md bg-gradient-to-t from-accent to-accent/40"
                        style={{ height: `${h}%` }}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="md:col-span-2 rounded-xl border border-border-subtle p-4 bg-bg-secondary/50">
                <div className="text-xs font-medium mb-3">Recent invoices</div>
                <div className="space-y-2.5">
                  {[
                    { id: 'INV-2841', status: 'Verified', ok: true },
                    { id: 'INV-2840', status: 'Processing', ok: false },
                    { id: 'INV-2839', status: 'Verified', ok: true },
                  ].map((row) => (
                    <div key={row.id} className="flex justify-between items-center text-[10px]">
                      <span className="font-medium">{row.id}</span>
                      <span
                        className={`px-1.5 py-0.5 rounded-full ${
                          row.ok ? 'bg-neutral-200 text-text-primary dark:bg-neutral-800' : 'bg-neutral-100 text-text-secondary dark:bg-neutral-900'
                        }`}
                      >
                        {row.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AutoInvoiceMock({ embedded = false }: { embedded?: boolean }) {
  const box = embedded
    ? 'text-left'
    : 'rounded-xl border border-border-subtle bg-bg-primary/95 backdrop-blur-md p-4 shadow-2xl text-left';
  return (
    <div className={box}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold">Auto extract</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-neutral-200 text-text-primary dark:bg-neutral-800 font-medium">
          Active
        </span>
      </div>
      <div className="space-y-2 text-xs">
        {[
          ['Source', 'PDF / Image upload'],
          ['Firm', 'Sharma & Associates'],
          ['Extraction', 'Line items + GST fields'],
          ['Validation', 'GSTIN + tax slab check'],
          ['Export', 'Tally / Excel / GSTR'],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-1.5 border-b border-border-subtle last:border-0">
            <span className="text-text-secondary">{k}</span>
            <span className="font-medium text-right">{v}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 p-2.5 rounded-lg bg-bg-secondary border border-dashed border-border-subtle">
        <Upload className="w-4 h-4 text-text-secondary shrink-0" />
        <span className="text-[11px] text-text-secondary">Drop invoices | AI processes in seconds</span>
      </div>
    </div>
  );
}

export function BillVerifyMock({ embedded = false }: { embedded?: boolean }) {
  const outer = embedded
    ? 'text-left'
    : 'rounded-xl border border-border-subtle bg-bg-primary/95 backdrop-blur-md shadow-2xl overflow-hidden text-left';
  return (
    <div className={outer}>
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold">GSTR-3B · Jan 2026</div>
          <div className="text-[11px] text-text-secondary mt-0.5">Sharma Textiles Pvt Ltd</div>
        </div>
        <span className="text-[10px] px-2 py-1 rounded-full bg-neutral-100 text-text-secondary dark:bg-neutral-900 font-medium">
          Review
        </span>
      </div>
      <div className="p-4 space-y-3 text-xs">
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 rounded-lg bg-bg-secondary border border-border-subtle">
            <div className="text-text-secondary">Taxable amount</div>
            <div className="text-base font-semibold mt-1 tabular-nums">₹ 12,48,500</div>
          </div>
          <div className="p-2.5 rounded-lg bg-bg-secondary border border-border-subtle">
            <div className="text-text-secondary">Total GST</div>
            <div className="text-base font-semibold mt-1 tabular-nums">₹ 2,24,730</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {['CGST matched', 'SGST matched', 'E-way linked'].map((t) => (
            <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-bg-secondary border border-border-subtle text-[10px]">
              <Check className="w-3 h-3" /> {t}
            </span>
          ))}
        </div>
        <button type="button" className="w-full py-2 rounded-lg bg-accent text-accent-foreground text-sm font-medium">
          Verify & approve bill
        </button>
      </div>
    </div>
  );
}

export function MultiFirmMock({ embedded = false }: { embedded?: boolean }) {
  const box = embedded ? 'text-left' : 'rounded-xl border border-border-subtle bg-bg-primary/95 backdrop-blur-md p-4 shadow-2xl text-left';
  return (
    <div className={box}>
      <div className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4" /> Client firms
      </div>
      <div className="space-y-2">
        {[
          { name: 'Sharma & Associates', bills: 248, active: true },
          { name: 'Patel Industries', bills: 186, active: false },
          { name: 'Mehta Exports LLP', bills: 92, active: false },
        ].map((firm) => (
          <div
            key={firm.name}
            className={`flex items-center justify-between p-2.5 rounded-lg border text-xs ${
              firm.active ? 'border-text-primary bg-bg-secondary' : 'border-border-subtle'
            }`}
          >
            <div>
              <div className="font-medium">{firm.name}</div>
              <div className="text-text-secondary text-[10px] mt-0.5">{firm.bills} bills this month</div>
            </div>
            {firm.active && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent text-accent-foreground">Active</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function GstComplianceMock({ embedded = false }: { embedded?: boolean }) {
  const box = embedded ? 'text-left text-xs' : 'rounded-xl border border-border-subtle bg-bg-primary/95 backdrop-blur-md p-4 shadow-2xl text-left text-xs';
  return (
    <div className={box}>
      <div className="font-semibold text-sm mb-3">GST compliance check</div>
      <div className="space-y-2">
        {[
          ['GSTIN 27AABCS1429B1Z5', 'Active'],
          ['GSTR-1 filing', 'Due 11 Mar'],
          ['E-way bills linked', '18 documents'],
          ['ITC match score', '99.2%'],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between py-1.5 border-b border-border-subtle last:border-0">
            <span className="text-text-secondary">{k}</span>
            <span className="font-medium text-text-primary">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

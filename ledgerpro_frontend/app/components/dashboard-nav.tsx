'use client';

import React from 'react';
import {
  LayoutDashboard,
  FileText,
  Globe,
  Truck,
  Database,
  Settings as SettingsIcon,
} from 'lucide-react';

export type TabType = 'overview' | 'invoices' | 'import-export' | 'e-way-bills' | 'vault' | 'settings';

const NAV_ITEMS: { id: TabType; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'invoices', label: 'Invoices', icon: FileText },
  { id: 'import-export', label: 'Import-Export', icon: Globe },
  { id: 'e-way-bills', label: 'E-way Bills', icon: Truck },
  { id: 'vault', label: 'Cloud Vault', icon: Database },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
];

interface DashboardNavProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  onNavigate?: () => void;
  layout?: 'vertical' | 'drawer';
}

export default function DashboardNav({
  activeTab,
  onTabChange,
  onNavigate,
  layout = 'vertical',
}: DashboardNavProps) {
  const handleClick = (tab: TabType) => {
    onTabChange(tab);
    onNavigate?.();
  };

  return (
    <nav className={layout === 'vertical' ? 'space-y-1.5' : 'space-y-1'}>
      {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => handleClick(id)}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-semibold transition-colors ${
            activeTab === id
              ? 'bg-accent text-accent-foreground'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-primary/50'
          }`}
        >
          <Icon className="w-4.5 h-4.5" /> {label}
        </button>
      ))}
    </nav>
  );
}

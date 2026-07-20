'use client';

import React from 'react';
import {
  LayoutDashboard,
  FileText,
  Globe,
  Truck,
  Database,
  Activity,
} from 'lucide-react';

export type TabType = 'overview' | 'activity' | 'invoices' | 'import-export' | 'e-way-bills' | 'vault' | 'settings';

const NAV_ITEMS: { id: TabType; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'activity', label: 'Activity', icon: Activity },
  { id: 'invoices', label: 'Invoices', icon: FileText },
  { id: 'import-export', label: 'Import-Export', icon: Globe },
  { id: 'e-way-bills', label: 'E-way Bills', icon: Truck },
  { id: 'vault', label: 'Cloud Vault', icon: Database },
];

interface DashboardNavProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  onNavigate?: () => void;
  layout?: 'vertical' | 'drawer';
  showActivity?: boolean;
}

export default function DashboardNav({
  activeTab,
  onTabChange,
  onNavigate,
  layout = 'vertical',
  showActivity = false,
}: DashboardNavProps) {
  const handleClick = (tab: TabType) => {
    onTabChange(tab);
    onNavigate?.();
  };

  const navItems = showActivity
    ? NAV_ITEMS
    : NAV_ITEMS.filter((item) => item.id !== 'activity');

  return (
    <nav className={layout === 'vertical' ? 'space-y-1.5' : 'space-y-1'}>
      {navItems.map(({ id, label, icon: Icon }) => (
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

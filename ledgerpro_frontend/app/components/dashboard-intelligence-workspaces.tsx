'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Building2,
  ChevronRight,
  RefreshCw,
  Shield,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { Firm } from '../auth-context';
import { getApiBaseUrl } from '../lib/api-url';

type WorkspaceKey =
  | 'owner-health'
  | 'accountant-clients'
  | 'cfo-intelligence'
  | 'auditor-evidence';

type UserRole = 'accountant' | 'owner' | 'auditor' | string;

interface RiskSummary {
  total: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  recent: Array<{
    id: number;
    severity: string;
    category: string;
    title: string;
    description: string;
    status: string;
    created_at: string;
  }>;
}

interface CashFlowForecast {
  as_of: string;
  current_balance: string;
  position_30d: string;
  position_60d: string;
  position_90d: string;
  pressure_day: number | null;
  pressure_amount: string | null;
  risk_explanation: string;
  health_score: string;
  avg_collection_days: string;
  avg_payment_days: string;
  daily_forecast?: Array<{
    date: string;
    balance: string | number;
  }>;
  top_delayed_receivables?: Array<Record<string, unknown>>;
  top_upcoming_payables?: Array<Record<string, unknown>>;
}

interface RiskSignalListItem {
  id: number;
  severity: string;
  category: string;
  status: string;
  title: string;
  description: string;
  entity_type: string;
  entity_id: number;
  created_at: string;
  vendor_id?: number | null;
  customer_id?: number | null;
}

interface ScoreRow {
  vendor_id?: number;
  vendor_name?: string;
  customer_id?: number;
  customer_name?: string;
  overall_score: string;
  breakdown?: Record<string, unknown>;
}

interface EvidenceGraph {
  root: string;
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  node_count: number;
  edge_count: number;
}

interface ActivityFeed {
  firm_id: number;
  firm_name: string;
  events: Array<{
    id: string;
    kind: string;
    action: string;
    actor_name: string | null;
    actor_role: string | null;
    resource_type: string | null;
    resource_id: number | null;
    timestamp: string;
    details?: Record<string, unknown>;
  }>;
}

interface ClientHealthRow {
  firm: Firm;
  riskSummary: RiskSummary | null;
  forecast: CashFlowForecast | null;
  riskScore: number;
}

interface DashboardIntelligenceWorkspacesProps {
  token: string | null;
  userRole?: string;
  selectedFirm: Firm | null;
  firms: Firm[];
  setSelectedFirm: (firm: Firm | null) => void;
}

const WORKSPACE_META: Record<
  WorkspaceKey,
  { label: string; description: string; roles: UserRole[] }
> = {
  'owner-health': {
    label: 'Business Owner',
    description: 'Financial health score, cash position, and live risk posture.',
    roles: ['owner', 'accountant'],
  },
  'accountant-clients': {
    label: 'Accountant',
    description: 'Cross-client queue sorted by open risk pressure.',
    roles: ['accountant'],
  },
  'cfo-intelligence': {
    label: 'CFO Intelligence',
    description: 'Forward-looking cash flow, concentration, and risk breakdowns.',
    roles: ['owner', 'accountant'],
  },
  'auditor-evidence': {
    label: 'Auditor',
    description: 'Evidence chains, risk provenance, and recent audit activity.',
    roles: ['auditor'],
  },
};

const SEVERITY_COLORS = ['#4f46e5', '#f59e0b', '#ef4444', '#22c55e', '#06b6d4', '#8b5cf6'];

function ThreeDotLoader() {
  return (
    <div className="inline-flex items-center gap-1.5 text-text-primary">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-current"
          style={{
            animation: 'dashboardDotBounce 1.2s ease-in-out infinite',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes dashboardDotBounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function formatCurrency(value: string | number | null | undefined, currency = 'INR') {
  const num = Number(value ?? 0);
  if (Number.isNaN(num)) return '--';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(num);
}

function formatNumber(value: string | number | null | undefined) {
  const num = Number(value ?? 0);
  if (Number.isNaN(num)) return '--';
  return new Intl.NumberFormat('en-IN').format(num);
}

function formatDateLabel(value?: string | null) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

function severityWeight(summary: RiskSummary | null) {
  if (!summary) return 0;
  const bySeverity = summary.by_severity || {};
  return (
    (bySeverity.critical || 0) * 100 +
    (bySeverity.high || 0) * 35 +
    (bySeverity.medium || 0) * 10 +
    (bySeverity.low || 0) * 3
  );
}

function SectionCard({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border-subtle bg-bg-secondary p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-[0.18em] text-text-secondary">{title}</h3>
          {subtitle ? <p className="mt-1 text-sm text-text-secondary">{subtitle}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function MetricCard({
  label,
  value,
  hint,
  accent = 'text-text-primary',
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-border-subtle bg-bg-primary/40 p-4">
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">{label}</div>
      <div className={`mt-2 text-2xl font-extrabold tracking-tight ${accent}`}>{value}</div>
      {hint ? <div className="mt-1 text-xs text-text-secondary">{hint}</div> : null}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-bg-primary/30 px-6 py-10 text-center">
      <Building2 className="h-8 w-8 text-text-secondary/70" />
      <p className="mt-3 max-w-lg text-sm text-text-secondary">{message}</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-text-primary">
      <AlertCircle className="mt-0.5 h-4 w-4 text-red-400" />
      <p>{message}</p>
    </div>
  );
}

export default function DashboardIntelligenceWorkspaces({
  token,
  userRole,
  selectedFirm,
  firms,
  setSelectedFirm,
}: DashboardIntelligenceWorkspacesProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const role = (userRole || 'accountant').toLowerCase();

  const accessibleWorkspaces = useMemo(() => {
    return (Object.keys(WORKSPACE_META) as WorkspaceKey[]).filter((key) =>
      WORKSPACE_META[key].roles.includes(role),
    );
  }, [role]);

  const preferredWorkspace = useMemo<WorkspaceKey>(() => {
    if (role === 'owner') return 'owner-health';
    if (role === 'auditor') return 'auditor-evidence';
    return 'accountant-clients';
  }, [role]);

  const requestedWorkspace = (searchParams.get('workspace') || '') as WorkspaceKey;
  const activeWorkspace = accessibleWorkspaces.includes(requestedWorkspace)
    ? requestedWorkspace
    : (accessibleWorkspaces[0] || preferredWorkspace);

  const [refreshTick, setRefreshTick] = useState(0);
  const [ownerHealth, setOwnerHealth] = useState<{
    loading: boolean;
    error: string | null;
    riskSummary: RiskSummary | null;
    forecast: CashFlowForecast | null;
    risks: RiskSignalListItem[];
  }>({
    loading: false,
    error: null,
    riskSummary: null,
    forecast: null,
    risks: [],
  });
  const [accountantView, setAccountantView] = useState<{
    loading: boolean;
    error: string | null;
    clients: ClientHealthRow[];
  }>({ loading: false, error: null, clients: [] });
  const [cfoView, setCfoView] = useState<{
    loading: boolean;
    error: string | null;
    riskSummary: RiskSummary | null;
    forecast: CashFlowForecast | null;
    vendorScores: ScoreRow[];
    customerScores: ScoreRow[];
  }>({
    loading: false,
    error: null,
    riskSummary: null,
    forecast: null,
    vendorScores: [],
    customerScores: [],
  });
  const [auditorView, setAuditorView] = useState<{
    loading: boolean;
    error: string | null;
    risks: RiskSignalListItem[];
    activity: ActivityFeed | null;
    selectedSignalId: number | null;
    graphLoading: boolean;
    graphError: string | null;
    graph: EvidenceGraph | null;
  }>({
    loading: false,
    error: null,
    risks: [],
    activity: null,
    selectedSignalId: null,
    graphLoading: false,
    graphError: null,
    graph: null,
  });

  useEffect(() => {
    if (!accessibleWorkspaces.length) return;
    if (requestedWorkspace === activeWorkspace) return;
    const next = new URLSearchParams(searchParams.toString());
    next.set('workspace', activeWorkspace);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [accessibleWorkspaces.length, activeWorkspace, pathname, requestedWorkspace, router, searchParams]);

  const apiFetch = useCallback(async <T,>(path: string, timeoutMs = 20000): Promise<T> => {
    const activeToken = token || localStorage.getItem('auth_token');
    if (!activeToken) {
      throw new Error('No authenticated session found.');
    }
    const apiUrl = getApiBaseUrl();
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${apiUrl}${path}`, {
        headers: {
          Authorization: `Bearer ${activeToken}`,
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed with ${res.status}`);
      }
      return res.json();
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new Error('Request timed out. Click Refresh workspace and try again.');
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }, [token]);

  const selectedFirmId = selectedFirm?.id ?? null;

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (activeWorkspace !== 'owner-health') return;
      if (!selectedFirmId) {
        setOwnerHealth({
          loading: false,
          error: null,
          riskSummary: null,
          forecast: null,
          risks: [],
        });
        return;
      }

      setOwnerHealth((prev) => ({ ...prev, loading: true, error: null }));
      try {
        // Prefer partial success over an infinite spinner if one endpoint stalls.
        const [riskSummaryResult, forecastResult, riskListResult] = await Promise.allSettled([
          apiFetch<RiskSummary>(`/api/firms/${selectedFirmId}/risk-summary/`),
          apiFetch<CashFlowForecast>(`/api/firms/${selectedFirmId}/cash-flow-forecast/`),
          apiFetch<{ results: RiskSignalListItem[] }>(
            `/api/firms/${selectedFirmId}/risk-signals/?status=open&page_size=6`,
          ),
        ]);

        if (cancelled) return;

        const riskSummary =
          riskSummaryResult.status === 'fulfilled' ? riskSummaryResult.value : null;
        const forecast = forecastResult.status === 'fulfilled' ? forecastResult.value : null;
        const risks =
          riskListResult.status === 'fulfilled' ? riskListResult.value.results || [] : [];

        const failures = [riskSummaryResult, forecastResult, riskListResult]
          .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
          .map((result) =>
            result.reason instanceof Error ? result.reason.message : 'Request failed',
          );

        if (!riskSummary && !forecast) {
          setOwnerHealth({
            loading: false,
            error: failures[0] || 'Failed to load owner health view.',
            riskSummary: null,
            forecast: null,
            risks: [],
          });
          return;
        }

        setOwnerHealth({
          loading: false,
          error: failures.length ? `Partial load: ${failures[0]}` : null,
          riskSummary,
          forecast,
          risks,
        });
      } catch (error) {
        if (!cancelled) {
          setOwnerHealth((prev) => ({
            ...prev,
            loading: false,
            error: error instanceof Error ? error.message : 'Failed to load owner health view.',
          }));
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace, apiFetch, refreshTick, selectedFirmId, token]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (activeWorkspace !== 'accountant-clients') return;
      const activeFirms = firms.filter((firm) => firm.status === 'active');
      if (!activeFirms.length) {
        setAccountantView({ loading: false, error: null, clients: [] });
        return;
      }

      setAccountantView((prev) => ({ ...prev, loading: true, error: null }));
      try {
        // Load clients in small batches so we don't block the API worker
        // (cash-flow-forecast can be computed on-demand and starve other views).
        const clientRows: ClientHealthRow[] = [];
        const batchSize = 3;
        for (let i = 0; i < activeFirms.length; i += batchSize) {
          if (cancelled) return;
          const batch = activeFirms.slice(i, i + batchSize);
          const batchRows = await Promise.all(
            batch.map(async (firm) => {
              const [riskSummary, forecast] = await Promise.all([
                apiFetch<RiskSummary>(`/api/firms/${firm.id}/risk-summary/`).catch(() => null),
                apiFetch<CashFlowForecast>(`/api/firms/${firm.id}/cash-flow-forecast/`).catch(
                  () => null,
                ),
              ]);
              return {
                firm,
                riskSummary,
                forecast,
                riskScore: severityWeight(riskSummary),
              } satisfies ClientHealthRow;
            }),
          );
          clientRows.push(...batchRows);
        }

        clientRows.sort((a, b) => {
          if (b.riskScore !== a.riskScore) return b.riskScore - a.riskScore;
          return Number(a.forecast?.health_score || 0) - Number(b.forecast?.health_score || 0);
        });

        if (!cancelled) {
          setAccountantView({ loading: false, error: null, clients: clientRows });
        }
      } catch (error) {
        if (!cancelled) {
          setAccountantView({
            loading: false,
            error: error instanceof Error ? error.message : 'Failed to load client health queue.',
            clients: [],
          });
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace, apiFetch, firms, refreshTick, token]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (activeWorkspace !== 'cfo-intelligence') return;
      if (!selectedFirmId) {
        setCfoView({
          loading: false,
          error: null,
          riskSummary: null,
          forecast: null,
          vendorScores: [],
          customerScores: [],
        });
        return;
      }

      setCfoView((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const [riskSummaryResult, forecastResult, vendorScoresResult, customerScoresResult] =
          await Promise.allSettled([
            apiFetch<RiskSummary>(`/api/firms/${selectedFirmId}/risk-summary/`),
            apiFetch<CashFlowForecast>(`/api/firms/${selectedFirmId}/cash-flow-forecast/`),
            apiFetch<{ results: ScoreRow[] }>(`/api/firms/${selectedFirmId}/vendor-scores/`),
            apiFetch<{ results: ScoreRow[] }>(`/api/firms/${selectedFirmId}/customer-scores/`),
          ]);

        if (cancelled) return;

        const riskSummary =
          riskSummaryResult.status === 'fulfilled' ? riskSummaryResult.value : null;
        const forecast = forecastResult.status === 'fulfilled' ? forecastResult.value : null;
        const vendorScores =
          vendorScoresResult.status === 'fulfilled' ? vendorScoresResult.value.results || [] : [];
        const customerScores =
          customerScoresResult.status === 'fulfilled'
            ? customerScoresResult.value.results || []
            : [];

        const failures = [
          riskSummaryResult,
          forecastResult,
          vendorScoresResult,
          customerScoresResult,
        ]
          .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
          .map((result) =>
            result.reason instanceof Error ? result.reason.message : 'Request failed',
          );

        if (!riskSummary && !forecast) {
          setCfoView({
            loading: false,
            error: failures[0] || 'Failed to load CFO intelligence view.',
            riskSummary: null,
            forecast: null,
            vendorScores: [],
            customerScores: [],
          });
          return;
        }

        setCfoView({
          loading: false,
          error: failures.length ? `Partial load: ${failures[0]}` : null,
          riskSummary,
          forecast,
          vendorScores,
          customerScores,
        });
      } catch (error) {
        if (!cancelled) {
          setCfoView((prev) => ({
            ...prev,
            loading: false,
            error: error instanceof Error ? error.message : 'Failed to load CFO intelligence view.',
          }));
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace, apiFetch, refreshTick, selectedFirmId, token]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (activeWorkspace !== 'auditor-evidence') return;
      if (!selectedFirmId) {
        setAuditorView((prev) => ({
          ...prev,
          loading: false,
          error: null,
          risks: [],
          activity: null,
          selectedSignalId: null,
          graph: null,
        }));
        return;
      }

      setAuditorView((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const [riskList, activity] = await Promise.all([
          apiFetch<{ results: RiskSignalListItem[] }>(
            `/api/firms/${selectedFirmId}/risk-signals/?status=all&page_size=12&ordering=-created_at`,
          ),
          apiFetch<ActivityFeed>(`/api/firms/${selectedFirmId}/activity?limit=25`),
        ]);
        const firstSignalId = riskList.results?.[0]?.id ?? null;
        if (!cancelled) {
          setAuditorView((prev) => ({
            ...prev,
            loading: false,
            error: null,
            risks: riskList.results || [],
            activity,
            selectedSignalId: prev.selectedSignalId && riskList.results.some((item) => item.id === prev.selectedSignalId)
              ? prev.selectedSignalId
              : firstSignalId,
          }));
        }
      } catch (error) {
        if (!cancelled) {
          setAuditorView((prev) => ({
            ...prev,
            loading: false,
            error: error instanceof Error ? error.message : 'Failed to load auditor evidence view.',
          }));
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace, apiFetch, refreshTick, selectedFirmId, token]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (activeWorkspace !== 'auditor-evidence') return;
      if (!selectedFirmId || !auditorView.selectedSignalId) {
        setAuditorView((prev) => ({ ...prev, graph: null, graphError: null, graphLoading: false }));
        return;
      }

      setAuditorView((prev) => ({ ...prev, graphLoading: true, graphError: null }));
      try {
        const graph = await apiFetch<EvidenceGraph>(
          `/api/firms/${selectedFirmId}/graph/risk-signal/${auditorView.selectedSignalId}/`,
        );
        if (!cancelled) {
          setAuditorView((prev) => ({ ...prev, graphLoading: false, graph }));
        }
      } catch (error) {
        if (!cancelled) {
          setAuditorView((prev) => ({
            ...prev,
            graphLoading: false,
            graphError: error instanceof Error ? error.message : 'Failed to load evidence graph.',
            graph: null,
          }));
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace, apiFetch, auditorView.selectedSignalId, selectedFirmId, token]);

  const setWorkspace = (workspace: WorkspaceKey) => {
    const next = new URLSearchParams(searchParams.toString());
    next.set('workspace', workspace);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  const ownerCurrency = selectedFirm?.base_currency || 'INR';
  const categoryBreakdown = useMemo(() => {
    const summary = cfoView.riskSummary;
    if (!summary) return [];
    return Object.entries(summary.by_category || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([name, value], index) => ({
        name: name.replaceAll('_', ' '),
        value,
        color: SEVERITY_COLORS[index % SEVERITY_COLORS.length],
      }));
  }, [cfoView.riskSummary]);

  const forecastSeries = useMemo(() => {
    return (cfoView.forecast?.daily_forecast || []).slice(0, 12).map((point) => ({
      date: formatDateLabel(point.date),
      balance: Number(point.balance || 0),
    }));
  }, [cfoView.forecast]);

  const evidenceNodes = auditorView.graph?.nodes || [];
  const evidenceTransactions = evidenceNodes.filter((node) => node.type === 'transaction');
  const evidenceParties = evidenceNodes.filter(
    (node) => node.type === 'vendor' || node.type === 'customer',
  );

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border-subtle bg-bg-secondary/70 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-text-secondary">
              Intelligence Dashboards
            </div>
            <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-text-primary">
              Role-aware operating views on top of `/dashboard`
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-text-secondary">
              These views stay inside the existing dashboard shell, consume live APIs from the intelligence
              phases, and follow the same auth gate already used for `/dashboard`.
            </p>
          </div>
          <button
            onClick={() => setRefreshTick((value) => value + 1)}
            className="inline-flex items-center gap-2 rounded-lg border border-border-subtle px-3 py-2 text-xs font-semibold text-text-secondary transition-colors hover:bg-bg-primary/40 hover:text-text-primary"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh workspace
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {(Object.keys(WORKSPACE_META) as WorkspaceKey[]).map((workspaceKey) => {
            const meta = WORKSPACE_META[workspaceKey];
            const canAccess = accessibleWorkspaces.includes(workspaceKey);
            const isActive = activeWorkspace === workspaceKey;
            return (
              <button
                key={workspaceKey}
                disabled={!canAccess}
                onClick={() => setWorkspace(workspaceKey)}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isActive
                    ? 'border-accent bg-accent/10'
                    : canAccess
                      ? 'border-border-subtle bg-bg-primary/30 hover:border-text-primary/30'
                      : 'border-border-subtle/60 bg-bg-primary/15 opacity-55'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-text-primary">{meta.label}</span>
                  {canAccess ? (
                    <ChevronRight className="h-4 w-4 text-text-secondary" />
                  ) : (
                    <Shield className="h-4 w-4 text-text-secondary" />
                  )}
                </div>
                <p className="mt-2 text-xs leading-5 text-text-secondary">{meta.description}</p>
                <div className="mt-3 text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">
                  {meta.roles.join(' / ')}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {!accessibleWorkspaces.length ? (
        <ErrorState message="This account role does not currently map to a dashboard workspace." />
      ) : null}

      {activeWorkspace === 'owner-health' ? (
        !selectedFirm ? (
          <EmptyState message="Select a firm to load the Business Owner health view." />
        ) : ownerHealth.loading && !ownerHealth.riskSummary && !ownerHealth.forecast ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-10 text-sm text-text-secondary">
            <ThreeDotLoader />
            <span>Loading owner health metrics…</span>
          </div>
        ) : ownerHealth.error && !ownerHealth.riskSummary && !ownerHealth.forecast ? (
          <ErrorState message={ownerHealth.error} />
        ) : (
          <div className="space-y-5">
            {ownerHealth.error ? <ErrorState message={ownerHealth.error} /> : null}
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Financial health"
                value={`${Math.round(Number(ownerHealth.forecast?.health_score || 0))}/100`}
                hint={`As of ${formatDateLabel(ownerHealth.forecast?.as_of)}`}
                accent="text-emerald-400"
              />
              <MetricCard
                label="Cash now"
                value={formatCurrency(ownerHealth.forecast?.current_balance, ownerCurrency)}
                hint="Current balance from live forecast snapshot"
              />
              <MetricCard
                label="30-day cash"
                value={formatCurrency(ownerHealth.forecast?.position_30d, ownerCurrency)}
                hint={
                  ownerHealth.forecast?.pressure_day
                    ? `Pressure expected in ${ownerHealth.forecast.pressure_day} days`
                    : 'No pressure day flagged'
                }
                accent={
                  Number(ownerHealth.forecast?.position_30d || 0) < 0 ? 'text-red-400' : 'text-text-primary'
                }
              />
              <MetricCard
                label="Open risks"
                value={formatNumber(ownerHealth.riskSummary?.by_status?.open || 0)}
                hint={`${formatNumber(ownerHealth.riskSummary?.total || 0)} total tracked signals`}
                accent="text-amber-400"
              />
            </div>

            <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
              <SectionCard
                title="Cash posture"
                subtitle={ownerHealth.forecast?.risk_explanation || 'Live 30/60/90 day view from cash-flow forecasting.'}
              >
                <div className="grid gap-4 md:grid-cols-3">
                  <MetricCard
                    label="60-day"
                    value={formatCurrency(ownerHealth.forecast?.position_60d, ownerCurrency)}
                    accent={
                      Number(ownerHealth.forecast?.position_60d || 0) < 0 ? 'text-red-400' : 'text-text-primary'
                    }
                  />
                  <MetricCard
                    label="90-day"
                    value={formatCurrency(ownerHealth.forecast?.position_90d, ownerCurrency)}
                    accent={
                      Number(ownerHealth.forecast?.position_90d || 0) < 0 ? 'text-red-400' : 'text-text-primary'
                    }
                  />
                  <MetricCard
                    label="Pressure amount"
                    value={formatCurrency(ownerHealth.forecast?.pressure_amount, ownerCurrency)}
                    hint="Locked to the current forecast snapshot"
                    accent="text-red-400"
                  />
                </div>
              </SectionCard>

              <SectionCard title="Risk mix" subtitle="Open-severity distribution from `/risk-summary/`.">
                <div className="space-y-3">
                  {(['critical', 'high', 'medium', 'low'] as const).map((severity) => {
                    const count = ownerHealth.riskSummary?.by_severity?.[severity] || 0;
                    const total = ownerHealth.riskSummary?.total || 1;
                    const width = `${Math.min(100, (count / total) * 100)}%`;
                    return (
                      <div key={severity}>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="font-semibold capitalize text-text-primary">{severity}</span>
                          <span className="text-text-secondary">{formatNumber(count)}</span>
                        </div>
                        <div className="h-2 rounded-full bg-bg-primary">
                          <div
                            className={`h-2 rounded-full ${
                              severity === 'critical'
                                ? 'bg-red-500'
                                : severity === 'high'
                                  ? 'bg-amber-500'
                                  : severity === 'medium'
                                    ? 'bg-blue-500'
                                    : 'bg-emerald-500'
                            }`}
                            style={{ width }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Recent alerts" subtitle="Most recent open signals from `/risk-signals/`.">
              {!ownerHealth.risks.length ? (
                <EmptyState message="No open risk signals for this firm." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-border-subtle text-left text-[11px] uppercase tracking-[0.18em] text-text-secondary">
                        <th className="pb-3 pr-4">Severity</th>
                        <th className="pb-3 pr-4">Signal</th>
                        <th className="pb-3 pr-4">Entity</th>
                        <th className="pb-3">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ownerHealth.risks.map((risk) => (
                        <tr key={risk.id} className="border-b border-border-subtle/70">
                          <td className="py-3 pr-4">
                            <span className="rounded-full border border-border-subtle px-2 py-1 text-[11px] font-semibold capitalize text-text-primary">
                              {risk.severity}
                            </span>
                          </td>
                          <td className="py-3 pr-4">
                            <div className="font-semibold text-text-primary">{risk.title}</div>
                            <div className="mt-1 text-xs text-text-secondary">{risk.description}</div>
                          </td>
                          <td className="py-3 pr-4 text-xs capitalize text-text-secondary">
                            {risk.entity_type.replaceAll('_', ' ')} #{risk.entity_id}
                          </td>
                          <td className="py-3 text-xs text-text-secondary">{formatDateLabel(risk.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>
          </div>
        )
      ) : null}

      {activeWorkspace === 'accountant-clients' ? (
        accountantView.loading && !accountantView.clients.length ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-10 text-sm text-text-secondary">
            <ThreeDotLoader />
            <span>Loading multi-client queue…</span>
          </div>
        ) : accountantView.error ? (
          <ErrorState message={accountantView.error} />
        ) : !accountantView.clients.length ? (
          <EmptyState message="No active client firms are available for this accountant view yet." />
        ) : (
          <SectionCard
            title="Risk-sorted client list"
            subtitle="Each row merges `/risk-summary/` with `/cash-flow-forecast/` and ranks clients by live pressure."
          >
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle text-left text-[11px] uppercase tracking-[0.18em] text-text-secondary">
                    <th className="pb-3 pr-4">Client</th>
                    <th className="pb-3 pr-4">Risk score</th>
                    <th className="pb-3 pr-4">Open risks</th>
                    <th className="pb-3 pr-4">Health</th>
                    <th className="pb-3 pr-4">30d cash</th>
                    <th className="pb-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {accountantView.clients.map((client) => (
                    <tr key={client.firm.id} className="border-b border-border-subtle/70">
                      <td className="py-3 pr-4">
                        <div className="font-semibold text-text-primary">{client.firm.name}</div>
                        <div className="mt-1 text-xs text-text-secondary">
                          {client.firm.city}, {client.firm.state}
                        </div>
                      </td>
                      <td className="py-3 pr-4 font-semibold text-red-400">{formatNumber(client.riskScore)}</td>
                      <td className="py-3 pr-4 text-text-primary">
                        {formatNumber(client.riskSummary?.by_status?.open || 0)}
                      </td>
                      <td className="py-3 pr-4 text-text-primary">
                        {Math.round(Number(client.forecast?.health_score || 0))}/100
                      </td>
                      <td className="py-3 pr-4 text-text-primary">
                        {formatCurrency(client.forecast?.position_30d, client.firm.base_currency || 'INR')}
                      </td>
                      <td className="py-3">
                        <button
                          onClick={() => {
                            setSelectedFirm(client.firm);
                            setWorkspace('cfo-intelligence');
                          }}
                          className="inline-flex items-center gap-2 rounded-lg border border-border-subtle px-3 py-1.5 text-xs font-semibold text-text-primary transition-colors hover:bg-bg-primary/40"
                        >
                          Open
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        )
      ) : null}

      {activeWorkspace === 'cfo-intelligence' ? (
        !selectedFirm ? (
          <EmptyState message="Select a firm to open the CFO Intelligence view." />
        ) : cfoView.loading && !cfoView.riskSummary && !cfoView.forecast ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-10 text-sm text-text-secondary">
            <ThreeDotLoader />
            <span>Loading CFO intelligence…</span>
          </div>
        ) : cfoView.error && !cfoView.riskSummary && !cfoView.forecast ? (
          <ErrorState message={cfoView.error} />
        ) : (
          <div className="space-y-5">
            {cfoView.error ? <ErrorState message={cfoView.error} /> : null}
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Current cash"
                value={formatCurrency(cfoView.forecast?.current_balance, ownerCurrency)}
                hint="Live base-currency balance"
              />
              <MetricCard
                label="Collection days"
                value={formatNumber(cfoView.forecast?.avg_collection_days)}
                hint="Average from receivable forecast inputs"
              />
              <MetricCard
                label="Payment days"
                value={formatNumber(cfoView.forecast?.avg_payment_days)}
                hint="Average from payable forecast inputs"
              />
              <MetricCard
                label="Total risks"
                value={formatNumber(cfoView.riskSummary?.total || 0)}
                hint="Across all signal categories"
                accent="text-amber-400"
              />
            </div>

            <div className="grid gap-5 xl:grid-cols-[1.4fr_0.9fr]">
              <SectionCard title="Daily forecast" subtitle="First twelve points from `/cash-flow-forecast/` daily series.">
                {forecastSeries.length ? (
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={forecastSeries}>
                        <defs>
                          <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.35} />
                            <stop offset="95%" stopColor="#4f46e5" stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.25} />
                        <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                        <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12 }}
                          formatter={(value) => formatCurrency(Number(value ?? 0), ownerCurrency)}
                        />
                        <Area
                          type="monotone"
                          dataKey="balance"
                          stroke="#818cf8"
                          fill="url(#forecastFill)"
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyState message="No daily forecast points are available yet for this firm." />
                )}
              </SectionCard>

              <SectionCard title="Risk breakdown" subtitle="Top categories from `/risk-summary/`.">
                {categoryBreakdown.length ? (
                  <div className="space-y-4">
                    <div className="h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={categoryBreakdown} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}>
                            {categoryBreakdown.map((entry) => (
                              <Cell key={entry.name} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12 }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="space-y-2">
                      {categoryBreakdown.map((entry) => (
                        <div key={entry.name} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2 text-text-primary">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                            <span className="capitalize">{entry.name}</span>
                          </div>
                          <span className="text-text-secondary">{formatNumber(entry.value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <EmptyState message="No risk-category data is available yet for this firm." />
                )}
              </SectionCard>
            </div>

            <div className="grid gap-5 xl:grid-cols-2">
              <SectionCard title="At-risk vendors" subtitle="Lowest-scoring vendors from `/vendor-scores/`.">
                {cfoView.vendorScores.length ? (
                  <div className="space-y-3">
                    {[...cfoView.vendorScores]
                      .sort((a, b) => Number(a.overall_score) - Number(b.overall_score))
                      .slice(0, 5)
                      .map((row) => (
                        <div key={row.vendor_id} className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-primary/30 px-4 py-3">
                          <div>
                            <div className="font-semibold text-text-primary">{row.vendor_name}</div>
                            <div className="text-xs text-text-secondary">Vendor score health</div>
                          </div>
                          <div className="text-lg font-bold text-red-400">{Math.round(Number(row.overall_score))}</div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <EmptyState message="Vendor scores have not been computed for this firm yet." />
                )}
              </SectionCard>

              <SectionCard title="Customer exposure" subtitle="Lowest-scoring customers from `/customer-scores/`.">
                {cfoView.customerScores.length ? (
                  <div className="space-y-3">
                    {[...cfoView.customerScores]
                      .sort((a, b) => Number(a.overall_score) - Number(b.overall_score))
                      .slice(0, 5)
                      .map((row) => (
                        <div key={row.customer_id} className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-primary/30 px-4 py-3">
                          <div>
                            <div className="font-semibold text-text-primary">{row.customer_name}</div>
                            <div className="text-xs text-text-secondary">Customer score health</div>
                          </div>
                          <div className="text-lg font-bold text-amber-400">{Math.round(Number(row.overall_score))}</div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <EmptyState message="Customer scores have not been computed for this firm yet." />
                )}
              </SectionCard>
            </div>
          </div>
        )
      ) : null}

      {activeWorkspace === 'auditor-evidence' ? (
        !selectedFirm ? (
          <EmptyState message="Select a firm to inspect the auditor evidence trail." />
        ) : auditorView.loading && !auditorView.risks.length ? (
          <div className="flex items-center justify-center gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-10 text-sm text-text-secondary">
            <ThreeDotLoader />
            <span>Loading audit evidence…</span>
          </div>
        ) : auditorView.error ? (
          <ErrorState message={auditorView.error} />
        ) : (
          <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
            <SectionCard title="Signals under review" subtitle="Recent risk signals from `/risk-signals/`.">
              {!auditorView.risks.length ? (
                <EmptyState message="No risk signals are available for evidence review." />
              ) : (
                <div className="space-y-3">
                  {auditorView.risks.map((risk) => {
                    const isActive = auditorView.selectedSignalId === risk.id;
                    return (
                      <button
                        key={risk.id}
                        onClick={() => setAuditorView((prev) => ({ ...prev, selectedSignalId: risk.id }))}
                        className={`w-full rounded-xl border p-4 text-left transition-all ${
                          isActive ? 'border-accent bg-accent/10' : 'border-border-subtle bg-bg-primary/25 hover:border-text-primary/30'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-semibold text-text-primary">{risk.title}</div>
                            <div className="mt-1 text-xs capitalize text-text-secondary">
                              {risk.severity} · {risk.category.replaceAll('_', ' ')}
                            </div>
                          </div>
                          <ChevronRight className="mt-0.5 h-4 w-4 text-text-secondary" />
                        </div>
                        <p className="mt-2 text-xs leading-5 text-text-secondary">{risk.description}</p>
                      </button>
                    );
                  })}
                </div>
              )}
            </SectionCard>

            <div className="space-y-5">
              <SectionCard
                title="Evidence graph"
                subtitle="Connected nodes and reconciliation edges from the graph traversal endpoint."
                actions={
                  auditorView.graphLoading ? (
                    <div className="flex items-center gap-2 text-xs text-text-secondary">
                      <ThreeDotLoader />
                      Loading graph
                    </div>
                  ) : null
                }
              >
                {auditorView.graphError ? (
                  <ErrorState message={auditorView.graphError} />
                ) : !auditorView.graph ? (
                  <EmptyState message="Select a risk signal to inspect its connected evidence chain." />
                ) : (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-3">
                      <MetricCard label="Nodes" value={formatNumber(auditorView.graph.node_count)} />
                      <MetricCard label="Edges" value={formatNumber(auditorView.graph.edge_count)} />
                      <MetricCard label="Transactions" value={formatNumber(evidenceTransactions.length)} />
                    </div>
                    <div className="grid gap-5 lg:grid-cols-2">
                      <div>
                        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">
                          Connected transactions
                        </div>
                        <div className="space-y-2">
                          {evidenceTransactions.slice(0, 8).map((node) => (
                            <div key={String(node.id)} className="rounded-lg border border-border-subtle bg-bg-primary/30 px-3 py-2 text-sm">
                              <div className="font-semibold text-text-primary">
                                {String(node.reference_number || `Transaction #${node.id}`)}
                              </div>
                              <div className="mt-1 text-xs capitalize text-text-secondary">
                                {String(node.txn_type || 'transaction')} · {formatCurrency(node.amount as string, String(node.currency || ownerCurrency))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">
                          Connected counterparties
                        </div>
                        <div className="space-y-2">
                          {evidenceParties.slice(0, 8).map((node) => (
                            <div key={`${String(node.type)}-${String(node.id)}`} className="rounded-lg border border-border-subtle bg-bg-primary/30 px-3 py-2 text-sm">
                              <div className="font-semibold text-text-primary">{String(node.name || `${node.type} #${node.id}`)}</div>
                              <div className="mt-1 text-xs capitalize text-text-secondary">{String(node.type)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </SectionCard>

              <SectionCard title="Recent activity" subtitle="Live activity from `/firms/{id}/activity`.">
                {!auditorView.activity?.events?.length ? (
                  <EmptyState message="No activity entries are available for this firm yet." />
                ) : (
                  <div className="space-y-3">
                    {auditorView.activity.events.slice(0, 8).map((event) => (
                      <div key={event.id} className="flex items-start justify-between gap-4 rounded-lg border border-border-subtle bg-bg-primary/25 px-4 py-3">
                        <div>
                          <div className="font-semibold capitalize text-text-primary">
                            {event.action.replaceAll('_', ' ')}
                          </div>
                          <div className="mt-1 text-xs text-text-secondary">
                            {event.actor_name || 'System'} · {event.actor_role || 'unknown'} · {event.resource_type || 'session'}
                          </div>
                        </div>
                        <div className="text-xs text-text-secondary">{formatDateLabel(event.timestamp)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          </div>
        )
      ) : null}
    </div>
  );
}

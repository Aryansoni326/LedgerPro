'use client';

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileSearch,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

type TrustVariant = 'risk-signal' | 'agent-answer' | 'reconciliation-exception';
type TrustSectionKey = 'conclusion' | 'confidence' | 'evidence' | 'reasoning' | 'recommendedAction';
type ActionTone = 'neutral' | 'recommended' | 'warning' | 'destructive';
type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired';

export interface ConfidenceModel {
  score: number;
  label: string;
  explanation: string;
  factors?: string[];
}

export interface EvidenceItem {
  id: string;
  label: string;
  value: string;
  supportingText?: string;
  sourceLabel: string;
  sourceHref?: string;
  sourceMeta?: string;
  emphasis?: 'default' | 'strong' | 'warning';
}

export interface ReasoningStep {
  id: string;
  title: string;
  detail: string;
}

export interface RecommendedActionModel {
  title: string;
  description: string;
  impactSummary: string;
  tone?: ActionTone;
  requiresApproval?: boolean;
  ctaLabel?: string;
}

export interface EvidenceBasedAIPanelProps {
  variant: TrustVariant;
  title?: string;
  badge?: string;
  conclusion: string;
  confidence: ConfidenceModel;
  evidence: EvidenceItem[];
  reasoning: ReasoningStep[];
  recommendedAction: RecommendedActionModel;
  defaultExpanded?: Partial<Record<TrustSectionKey, boolean>>;
  footer?: React.ReactNode;
}

export interface ApprovalChangeItem {
  id: string;
  label: string;
  before?: string;
  after: string;
  impact?: string;
}

export interface ApprovalReviewPanelProps {
  status?: ApprovalStatus;
  title?: string;
  actionLabel: string;
  businessSummary: string;
  subjectLabel: string;
  subjectValue: string;
  requestedBy: string;
  requestedAt: string;
  reason: string;
  changes: ApprovalChangeItem[];
  safeguards: string[];
  evidencePanel: Omit<EvidenceBasedAIPanelProps, 'footer'>;
  reviewNotes?: string;
  approveLabel?: string;
  rejectLabel?: string;
  onApprove?: () => void;
  onReject?: () => void;
}

const VARIANT_COPY: Record<
  TrustVariant,
  {
    label: string;
    icon: typeof ShieldCheck;
    accent: string;
    surface: string;
  }
> = {
  'risk-signal': {
    label: 'Risk Signal',
    icon: AlertTriangle,
    accent: 'text-amber-400',
    surface: 'bg-amber-500/10 border-amber-500/20',
  },
  'agent-answer': {
    label: 'Agent Answer',
    icon: Bot,
    accent: 'text-sky-400',
    surface: 'bg-sky-500/10 border-sky-500/20',
  },
  'reconciliation-exception': {
    label: 'Reconciliation Exception',
    icon: FileSearch,
    accent: 'text-violet-400',
    surface: 'bg-violet-500/10 border-violet-500/20',
  },
};

const ACTION_TONE_STYLES: Record<ActionTone, string> = {
  neutral: 'border-border-subtle bg-bg-primary/30',
  recommended: 'border-emerald-500/30 bg-emerald-500/10',
  warning: 'border-amber-500/30 bg-amber-500/10',
  destructive: 'border-red-500/30 bg-red-500/10',
};

function formatPercent(score: number) {
  return `${Math.round(score * 100)}%`;
}

function ExpandableSection({
  id,
  title,
  summary,
  defaultOpen = true,
  children,
}: {
  id: TrustSectionKey | string;
  title: string;
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="rounded-xl border border-border-subtle bg-bg-primary/30">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-start justify-between gap-4 px-4 py-4 text-left"
        aria-expanded={open}
        aria-controls={`${id}-panel`}
      >
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-text-secondary">{title}</div>
          <div className="mt-1 text-sm text-text-primary">{summary}</div>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-text-secondary" /> : <ChevronDown className="h-4 w-4 text-text-secondary" />}
      </button>
      {open ? (
        <div id={`${id}-panel`} className="border-t border-border-subtle px-4 py-4">
          {children}
        </div>
      ) : null}
    </section>
  );
}

export function EvidenceBasedAIPanel({
  variant,
  title,
  badge,
  conclusion,
  confidence,
  evidence,
  reasoning,
  recommendedAction,
  defaultExpanded,
  footer,
}: EvidenceBasedAIPanelProps) {
  const variantMeta = VARIANT_COPY[variant];
  const VariantIcon = variantMeta.icon;

  const conclusionSummary = conclusion;
  const confidenceSummary = `${confidence.label} · ${formatPercent(confidence.score)}`;
  const evidenceSummary = `${evidence.length} linked evidence ${evidence.length === 1 ? 'item' : 'items'}`;
  const reasoningSummary = reasoning.length
    ? reasoning[0].title
    : 'Reasoning available';
  const actionSummary = recommendedAction.title;

  return (
    <div className={`space-y-4 rounded-2xl border p-5 ${variantMeta.surface}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className={`inline-flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] ${variantMeta.accent}`}>
            <VariantIcon className="h-4 w-4" />
            {variantMeta.label}
            {badge ? <span className="rounded-full border border-current/20 px-2 py-0.5 text-[10px]">{badge}</span> : null}
          </div>
          {title ? <h3 className="mt-2 text-lg font-bold text-text-primary">{title}</h3> : null}
        </div>
      </div>

      <ExpandableSection
        id="conclusion"
        title="Conclusion"
        summary={conclusionSummary}
        defaultOpen={defaultExpanded?.conclusion ?? true}
      >
        <p className="text-sm leading-6 text-text-primary">{conclusion}</p>
      </ExpandableSection>

      <ExpandableSection
        id="confidence"
        title="Confidence"
        summary={confidenceSummary}
        defaultOpen={defaultExpanded?.confidence ?? true}
      >
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="h-2.5 flex-1 rounded-full bg-bg-primary">
              <div
                className="h-2.5 rounded-full bg-accent"
                style={{ width: `${Math.max(8, Math.min(100, confidence.score * 100))}%` }}
              />
            </div>
            <div className="text-sm font-semibold text-text-primary">{formatPercent(confidence.score)}</div>
          </div>
          <p className="text-sm text-text-secondary">{confidence.explanation}</p>
          {confidence.factors?.length ? (
            <ul className="space-y-2 text-sm text-text-secondary">
              {confidence.factors.map((factor) => (
                <li key={factor} className="flex gap-2">
                  <span className="mt-1 h-1.5 w-1.5 rounded-full bg-accent" />
                  <span>{factor}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </ExpandableSection>

      <ExpandableSection
        id="evidence"
        title="Evidence"
        summary={evidenceSummary}
        defaultOpen={defaultExpanded?.evidence ?? true}
      >
        <div className="space-y-3">
          {evidence.map((item) => (
            <div key={item.id} className="rounded-xl border border-border-subtle bg-bg-secondary px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">{item.label}</div>
                  <div className="mt-1 text-base font-semibold text-text-primary">{item.value}</div>
                  {item.supportingText ? <div className="mt-1 text-sm text-text-secondary">{item.supportingText}</div> : null}
                </div>
                <div className="text-right text-xs text-text-secondary">
                  {item.sourceHref ? (
                    <a href={item.sourceHref} className="font-semibold text-accent hover:underline">
                      {item.sourceLabel}
                    </a>
                  ) : (
                    <div className="font-semibold text-text-primary">{item.sourceLabel}</div>
                  )}
                  {item.sourceMeta ? <div className="mt-1">{item.sourceMeta}</div> : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      </ExpandableSection>

      <ExpandableSection
        id="reasoning"
        title="Reasoning"
        summary={reasoningSummary}
        defaultOpen={defaultExpanded?.reasoning ?? true}
      >
        <ol className="space-y-3">
          {reasoning.map((step, index) => (
            <li key={step.id} className="flex gap-3">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border-subtle bg-bg-secondary text-xs font-semibold text-text-primary">
                {index + 1}
              </div>
              <div>
                <div className="text-sm font-semibold text-text-primary">{step.title}</div>
                <div className="mt-1 text-sm leading-6 text-text-secondary">{step.detail}</div>
              </div>
            </li>
          ))}
        </ol>
      </ExpandableSection>

      <ExpandableSection
        id="recommendedAction"
        title="Recommended Action"
        summary={actionSummary}
        defaultOpen={defaultExpanded?.recommendedAction ?? true}
      >
        <div className={`rounded-xl border p-4 ${ACTION_TONE_STYLES[recommendedAction.tone || 'neutral']}`}>
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 h-4 w-4 text-accent" />
            <div className="space-y-2">
              <div className="text-sm font-semibold text-text-primary">{recommendedAction.title}</div>
              <div className="text-sm leading-6 text-text-secondary">{recommendedAction.description}</div>
              <div className="rounded-lg border border-border-subtle bg-bg-secondary px-3 py-2 text-sm text-text-primary">
                {recommendedAction.impactSummary}
              </div>
              {recommendedAction.requiresApproval ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-border-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Human approval required before LedgerPro acts
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </ExpandableSection>

      {footer ? <div>{footer}</div> : null}
    </div>
  );
}

export function ApprovalReviewPanel({
  status = 'pending',
  title = 'Approval Required',
  actionLabel,
  businessSummary,
  subjectLabel,
  subjectValue,
  requestedBy,
  requestedAt,
  reason,
  changes,
  safeguards,
  evidencePanel,
  reviewNotes,
  approveLabel = 'Approve action',
  rejectLabel = 'Reject action',
  onApprove,
  onReject,
}: ApprovalReviewPanelProps) {
  const statusLabel = useMemo(() => {
    if (status === 'approved') return 'Approved';
    if (status === 'rejected') return 'Rejected';
    if (status === 'expired') return 'Expired';
    return 'Pending Review';
  }, [status]);

  return (
    <div className="space-y-4 rounded-2xl border border-border-subtle bg-bg-secondary p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-text-secondary">Action Approval</div>
          <h3 className="mt-2 text-lg font-bold text-text-primary">{title}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">{businessSummary}</p>
        </div>
        <div className="rounded-full border border-border-subtle px-3 py-1 text-xs font-semibold text-text-primary">
          {statusLabel}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-border-subtle bg-bg-primary/30 p-4">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">Action</div>
          <div className="mt-2 text-sm font-semibold text-text-primary">{actionLabel}</div>
        </div>
        <div className="rounded-xl border border-border-subtle bg-bg-primary/30 p-4">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">{subjectLabel}</div>
          <div className="mt-2 text-sm font-semibold text-text-primary">{subjectValue}</div>
        </div>
        <div className="rounded-xl border border-border-subtle bg-bg-primary/30 p-4">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">Requested by</div>
          <div className="mt-2 text-sm font-semibold text-text-primary">{requestedBy}</div>
          <div className="mt-1 text-xs text-text-secondary">{requestedAt}</div>
        </div>
      </div>

      <ExpandableSection
        id="approval-what-you-approve"
        title="What you are approving"
        summary={actionLabel}
        defaultOpen
      >
        <div className="space-y-3">
          <p className="text-sm leading-6 text-text-primary">{reason}</p>
          <div className="space-y-3">
            {changes.map((change) => (
              <div key={change.id} className="rounded-xl border border-border-subtle bg-bg-primary/30 p-4">
                <div className="text-sm font-semibold text-text-primary">{change.label}</div>
                <div className="mt-2 grid gap-3 md:grid-cols-2">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">Before</div>
                    <div className="mt-1 text-sm text-text-primary">{change.before || 'No existing value'}</div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">After</div>
                    <div className="mt-1 text-sm text-text-primary">{change.after}</div>
                  </div>
                </div>
                {change.impact ? <div className="mt-3 text-sm text-text-secondary">{change.impact}</div> : null}
              </div>
            ))}
          </div>
        </div>
      </ExpandableSection>

      <EvidenceBasedAIPanel
        {...evidencePanel}
        footer={
          safeguards.length ? (
            <div className="rounded-xl border border-border-subtle bg-bg-primary/30 p-4">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">Safeguards</div>
              <ul className="mt-3 space-y-2 text-sm text-text-secondary">
                {safeguards.map((item) => (
                  <li key={item} className="flex gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-400" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null
        }
      />

      <ExpandableSection
        id="approval-decision"
        title="Decision"
        summary="Approve only if the change, evidence, and business impact all make sense to you."
        defaultOpen
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm leading-6 text-text-primary">
            Approving will let LedgerPro execute the action exactly as described above. Rejecting will leave the underlying record unchanged.
          </div>
          {reviewNotes ? (
            <div className="rounded-xl border border-border-subtle bg-bg-primary/30 p-4 text-sm text-text-secondary">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-secondary">Reviewer notes</div>
              <div className="mt-2 text-text-primary">{reviewNotes}</div>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-3">
            {onReject ? (
              <button
                type="button"
                onClick={onReject}
                className="inline-flex items-center gap-2 rounded-lg border border-border-subtle px-4 py-2 text-sm font-semibold text-text-primary transition-colors hover:bg-bg-primary/40"
              >
                {rejectLabel}
              </button>
            ) : null}
            {onApprove ? (
              <button
                type="button"
                onClick={onApprove}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground transition-opacity hover:opacity-90"
              >
                {approveLabel}
              </button>
            ) : null}
          </div>
        </div>
      </ExpandableSection>
    </div>
  );
}

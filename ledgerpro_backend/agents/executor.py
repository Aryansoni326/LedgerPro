"""
Agent executor — runs a query through the correct specialised agent.

Architecture:
    1. Router classifies the query → agent type.
    2. Executor loads the agent's system prompt + allowed tools.
    3. Tool calls are executed, results recorded as AgentAction rows.
    4. Write-tool results are captured as PendingApproval (never executed).
    5. Final response is assembled in the Evidence-Based AI schema:
       conclusion → confidence → evidence → reasoning → recommended_action.

This module does NOT call any LLM. It is a deterministic, rule-based agent
that selects tools, calls them, and synthesises a structured response from
the real data returned.  An LLM-based version would swap out `_synthesise`
for a prompt-based generator, but the tool-calling and approval gating
remain identical.
"""
import logging
import time
from decimal import Decimal

from django.utils import timezone

from .models import AgentAction, AgentConversation, ChatSession, PendingApproval
from .tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Agent definitions: system prompts + tool allowlists
# ═══════════════════════════════════════════════════════════════════════

AGENT_DEFINITIONS: dict[str, dict] = {
    'finance': {
        'display_name': 'Finance Agent',
        'system_prompt': (
            "You are the Finance Agent for an SME accounting platform. "
            "You help users understand their cash position, receivables, "
            "payables, and cash-flow forecasts. You ONLY use data returned "
            "by your tools — never invent numbers. Every claim must cite "
            "the tool call that produced it."
        ),
        'tools': [
            'cashflow_forecast',
            'overdue_receivables',
            'payables_due',
            'vendor_scores',
            'customer_scores',
            'vendor_detail',
            'customer_detail',
            'biggest_expenses',
            'customers_owing',
            'profit_analysis',
            'transaction_detail',
            'send_payment_reminder',
        ],
    },
    'compliance': {
        'display_name': 'Compliance Agent',
        'system_prompt': (
            "You are the Compliance Agent. You monitor risk signals, "
            "reconciliation exceptions, and vendor anomalies. You help "
            "users understand compliance gaps and recommend remediation. "
            "You ONLY use data returned by your tools — never invent data."
        ),
        'tools': [
            'risk_summary',
            'reconciliation_status',
            'recon_exceptions',
            'vendor_scores',
            'vendor_detail',
            'flag_transaction',
            'update_risk_status',
        ],
    },
    'cfo': {
        'display_name': 'CFO Agent',
        'system_prompt': (
            "You are the CFO Agent — a strategic advisor. You synthesise "
            "cash-flow forecasts, risk landscape, vendor/customer health, "
            "and reconciliation status into executive-level insights. "
            "You ONLY use data returned by your tools — never fabricate "
            "numbers or projections."
        ),
        'tools': [
            'cashflow_forecast',
            'risk_summary',
            'reconciliation_status',
            'vendor_scores',
            'customer_scores',
            'overdue_receivables',
            'payables_due',
            'biggest_expenses',
            'customers_owing',
            'profit_analysis',
        ],
    },
    'audit': {
        'display_name': 'Audit Agent',
        'system_prompt': (
            "You are the Audit Agent. You help users trace transactions, "
            "verify reconciliation integrity, review audit trails, and "
            "investigate reconciliation exceptions. You ONLY reference "
            "data returned by your tools."
        ),
        'tools': [
            'audit_trail',
            'reconciliation_status',
            'recon_exceptions',
            'vendor_detail',
            'customer_detail',
            'flag_transaction',
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Router — deterministic keyword classifier
# ═══════════════════════════════════════════════════════════════════════

_ROUTE_RULES: list[tuple[str, list[str]]] = [
    ('compliance', [
        'risk', 'compliance', 'gst', 'mismatch', 'anomaly', 'signal',
        'flag', 'suspicious', 'duplicate', 'alert',
    ]),
    ('audit', [
        'audit', 'trail', 'trace', 'investigate', 'reconcil', 'exception',
        'who changed', 'who modified', 'history', 'log',
    ]),
    ('cfo', [
        'cfo', 'executive', 'strategic', 'overview', 'summary', 'dashboard',
        'health', 'outlook', 'board', 'report',
    ]),
    ('finance', [
        'cash', 'forecast', 'receivable', 'payable', 'invoice', 'payment',
        'vendor', 'customer', 'score', 'balance', 'overdue', 'collection',
        'remind',
    ]),
]


def route_query(query: str) -> str:
    """Classify a user query to one of the four agent types.

    Uses a scored keyword match — the agent with the most keyword hits wins.
    Ties are broken by priority order (compliance > audit > cfo > finance).
    Falls back to 'finance' if no keywords match.
    """
    q_lower = query.lower()
    scores: dict[str, int] = {}
    for agent_type, keywords in _ROUTE_RULES:
        score = sum(1 for kw in keywords if kw in q_lower)
        scores[agent_type] = score

    if max(scores.values()) == 0:
        return 'finance'

    return max(scores, key=lambda k: scores[k])


# ═══════════════════════════════════════════════════════════════════════
# Tool selection — pick the right tools for the query
# ═══════════════════════════════════════════════════════════════════════

_TOOL_TRIGGERS: dict[str, list[str]] = {
    'cashflow_forecast': ['cash', 'forecast', 'position', 'pressure', 'balance', 'outlook'],
    'risk_summary': ['risk', 'signal', 'alert', 'compliance', 'severity'],
    'reconciliation_status': ['reconcil', 'match', 'exception'],
    'recon_exceptions': ['exception', 'mismatch', 'unresolved', 'reconcil'],
    'vendor_scores': ['vendor', 'supplier', 'score', 'trust'],
    'customer_scores': ['customer', 'client', 'score', 'credit'],
    'vendor_detail': ['vendor detail', 'vendor breakdown', 'supplier detail'],
    'customer_detail': ['customer detail', 'client breakdown', 'customer breakdown'],
    'overdue_receivables': ['overdue', 'receivable', 'late payment', 'delayed', 'outstanding'],
    'payables_due': ['payable', 'upcoming payment', 'vendor payment', 'due'],
    'audit_trail': ['audit', 'trail', 'log', 'history', 'who'],
    'biggest_expenses': ['expense', 'biggest', 'largest', 'spending', 'cost', 'spent'],
    'customers_owing': ['owe', 'owing', 'who owes', 'debt', 'debtors', 'outstanding'],
    'profit_analysis': ['profit', 'loss', 'margin', 'p&l', 'why.*decrease', 'revenue'],
    'transaction_detail': [],  # only called via drill-down context
    'flag_transaction': ['flag', 'suspicious', 'investigate transaction'],
    'send_payment_reminder': ['remind', 'collection', 'follow up', 'chase'],
    'update_risk_status': ['dismiss', 'acknowledge', 'resolve signal', 'close signal'],
}


def select_tools(query: str, allowed_tools: list[str]) -> list[str]:
    """Pick which tools to call based on query keywords, limited to allowed set."""
    q_lower = query.lower()
    selected = []
    for tool_name in allowed_tools:
        triggers = _TOOL_TRIGGERS.get(tool_name, [])
        if any(t in q_lower for t in triggers):
            selected.append(tool_name)

    # Always include at least one tool — fallback to the first allowed read tool
    if not selected:
        for t in allowed_tools:
            if not TOOL_REGISTRY[t]['write']:
                selected.append(t)
                break

    return selected


# ═══════════════════════════════════════════════════════════════════════
# Executor — run the agent
# ═══════════════════════════════════════════════════════════════════════

def _resolve_followup_context(
    session: ChatSession | None, query: str, firm_id: int,
    allowed_tools: list[str],
) -> tuple[list[str], dict]:
    """Resolve follow-up references using prior conversation context.

    Detects drill-down patterns like "show me the invoices" or "which ones"
    and injects entity IDs from the prior turn's evidence so the correct
    tools are selected with the right parameters.
    """
    extra_kwargs = {}
    extra_tools = []

    if not session:
        return extra_tools, extra_kwargs

    # Get the last completed turn's evidence
    last_turn = (
        AgentConversation.objects.filter(session=session, completed_at__isnull=False)
        .order_by('-created_at')
        .first()
    )
    if not last_turn or not last_turn.response:
        return extra_tools, extra_kwargs

    q_lower = query.lower()
    is_followup = any(kw in q_lower for kw in [
        'show me', 'which', 'those', 'the invoices', 'the transactions',
        'why', 'detail', 'drill', 'more about', 'explain', 'responsible',
        'break down', 'elaborate', 'specifics',
    ])

    if not is_followup:
        return extra_tools, extra_kwargs

    # Extract entity_refs from prior evidence for deep-linking
    prior_evidence = last_turn.response.get('evidence', [])
    prior_entity_refs = []
    for ev in prior_evidence:
        data = ev.get('data', {})
        if isinstance(data, dict):
            prior_entity_refs.extend(data.get('entity_refs', []))
            # Also extract from nested items
            for item in data.get('items', []):
                if isinstance(item, dict) and 'id' in item:
                    prior_entity_refs.append({
                        'type': 'transaction', 'id': item['id'],
                        'url': f'/transactions/{item["id"]}',
                    })
            for item in data.get('top_delayed_receivables', []):
                if isinstance(item, dict) and 'id' in item:
                    prior_entity_refs.append({
                        'type': 'transaction', 'id': item['id'],
                        'url': f'/transactions/{item["id"]}',
                    })
            for item in data.get('top_upcoming_payables', []):
                if isinstance(item, dict) and 'id' in item:
                    prior_entity_refs.append({
                        'type': 'transaction', 'id': item['id'],
                        'url': f'/transactions/{item["id"]}',
                    })

    # Store prior context for the synthesiser
    extra_kwargs['_prior_entity_refs'] = prior_entity_refs
    extra_kwargs['_prior_tools'] = last_turn.response.get('tools_called', [])
    extra_kwargs['_prior_conclusion'] = last_turn.response.get('conclusion', '')

    # If the prior turn called cashflow_forecast and user asks "why" / "show me",
    # drill into overdue_receivables and payables_due
    prior_tools = set(last_turn.response.get('tools_called', []))
    if {'cashflow_forecast'} & prior_tools and any(
        kw in q_lower for kw in ['why', 'invoices', 'responsible', 'detail', 'show']
    ):
        if 'overdue_receivables' in allowed_tools:
            extra_tools.append('overdue_receivables')
        if 'payables_due' in allowed_tools:
            extra_tools.append('payables_due')

    # If prior turn had overdue_receivables and user asks "show me" / "which customers"
    if {'overdue_receivables'} & prior_tools and any(
        kw in q_lower for kw in ['customer', 'who', 'which', 'show']
    ):
        if 'customers_owing' in allowed_tools:
            extra_tools.append('customers_owing')

    return extra_tools, extra_kwargs


def execute_agent(
    *,
    firm_id: int,
    user,
    query: str,
    agent_type: str | None = None,
    session_id: str | None = None,
) -> AgentConversation:
    """Run a query through the appropriate agent.

    1. Route query → agent type (or use explicit override).
    2. Resolve follow-up context from prior session turns.
    3. Select tools based on query + context.
    4. Execute each tool, record AgentAction rows.
    5. For write tools, create PendingApproval instead of executing.
    6. Synthesise structured response with deep-linkable entity_refs.
    """
    from firms.models import Firm

    request_start = time.monotonic()
    firm = Firm.objects.get(pk=firm_id)

    routed = agent_type or route_query(query)
    defn = AGENT_DEFINITIONS[routed]

    # Session management
    session = None
    turn_number = 1
    if session_id:
        try:
            session = ChatSession.objects.get(pk=session_id, firm=firm, user=user)
            turn_number = (
                AgentConversation.objects.filter(session=session).count() + 1
            )
        except ChatSession.DoesNotExist:
            session = None

    if not session:
        session = ChatSession.objects.create(firm=firm, user=user)

    conv = AgentConversation.objects.create(
        firm=firm,
        user=user,
        session=session,
        turn_number=turn_number,
        agent_type=routed,
        query=query,
        routed_by='explicit' if agent_type else 'auto',
    )

    # Resolve follow-up context (only if this is not the first turn)
    prior_session = session if turn_number > 1 else None
    followup_tools, followup_kwargs = _resolve_followup_context(
        prior_session, query, firm_id, defn['tools'],
    )

    # Select and execute tools
    tools_to_call = select_tools(query, defn['tools'])
    for ft in followup_tools:
        if ft not in tools_to_call:
            tools_to_call.append(ft)

    # If follow-up context injected tools, prioritise them (move to front)
    if followup_tools:
        ordered = [t for t in followup_tools if t in tools_to_call]
        ordered += [t for t in tools_to_call if t not in followup_tools]
        tools_to_call = ordered

    tool_results: dict[str, dict] = {}
    pending_approvals: list[dict] = []

    for tool_name in tools_to_call:
        tool_entry = TOOL_REGISTRY[tool_name]
        fn = tool_entry['fn']
        tool_input = {'firm_id': firm_id}

        start = time.monotonic()
        try:
            result = fn(**tool_input)
        except Exception as exc:
            logger.exception("Tool %s failed for firm %s", tool_name, firm_id)
            result = {'error': str(exc)}
        duration_ms = int((time.monotonic() - start) * 1000)

        AgentAction.objects.create(
            conversation=conv,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_result=result,
            duration_ms=duration_ms,
        )

        if result.get('_requires_approval'):
            approval = PendingApproval.objects.create(
                conversation=conv,
                firm=firm,
                proposed_action=result['proposed_action'],
                action_params=result.get('action_params', {}),
                reason=result.get('reason', ''),
            )
            pending_approvals.append({
                'approval_id': str(approval.id),
                'action': result['proposed_action'],
                'reason': result.get('reason', ''),
                'status': 'pending_human_approval',
            })
        else:
            tool_results[tool_name] = result

    # Synthesise
    response = _synthesise(
        agent_type=routed,
        query=query,
        tool_results=tool_results,
        pending_approvals=pending_approvals,
        system_prompt=defn['system_prompt'],
        prior_entity_refs=followup_kwargs.get('_prior_entity_refs', []),
    )

    total_ms = int((time.monotonic() - request_start) * 1000)

    conv.response = response
    conv.completed_at = timezone.now()
    conv.latency_ms = total_ms
    conv.save(update_fields=['response', 'completed_at', 'latency_ms'])

    # Touch session
    session.save(update_fields=['last_active_at'])

    return conv


# ═══════════════════════════════════════════════════════════════════════
# Response synthesiser — Evidence-Based AI schema
# ═══════════════════════════════════════════════════════════════════════

def _synthesise(
    *,
    agent_type: str,
    query: str,
    tool_results: dict[str, dict],
    pending_approvals: list[dict],
    system_prompt: str,
    prior_entity_refs: list[dict] | None = None,
) -> dict:
    """Build the Evidence-Based AI structured response.

    Schema: conclusion → confidence → evidence → reasoning → recommended_action
            + entity_refs (deep-linkable IDs for every claim)

    Every factual claim is traceable to a specific invoice/transaction/signal
    via the entity_refs array. The frontend can use these to build deep-links.
    """
    evidence: list[dict] = []
    reasoning_parts: list[str] = []
    conclusion_parts: list[str] = []
    recommendations: list[str] = []
    all_entity_refs: list[dict] = list(prior_entity_refs or [])
    confidence = Decimal("0.85")

    for tool_name, result in tool_results.items():
        if 'error' in result:
            evidence.append({
                'source': tool_name, 'status': 'error', 'detail': result['error'],
            })
            confidence -= Decimal("0.10")
            continue

        evidence.append({'source': tool_name, 'data': result})

        # Collect entity_refs from tool results
        if isinstance(result, dict):
            all_entity_refs.extend(result.get('entity_refs', []))

        if tool_name == 'cashflow_forecast':
            _process_cashflow(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'risk_summary':
            _process_risk(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'reconciliation_status':
            _process_recon(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name in ('vendor_scores', 'customer_scores'):
            _process_scores(tool_name, result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'overdue_receivables':
            _process_overdue(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'payables_due':
            _process_payables(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'audit_trail':
            _process_audit(result, conclusion_parts, reasoning_parts)
        elif tool_name == 'recon_exceptions':
            _process_exceptions(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'biggest_expenses':
            _process_expenses(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'customers_owing':
            _process_customers_owing(result, conclusion_parts, reasoning_parts, recommendations)
        elif tool_name == 'profit_analysis':
            _process_profit(result, conclusion_parts, reasoning_parts, recommendations)

    if pending_approvals:
        for pa in pending_approvals:
            recommendations.append(
                f"[REQUIRES APPROVAL] {pa['action']}: {pa['reason']} "
                f"(Approval ID: {pa['approval_id']})"
            )

    if not tool_results:
        confidence = Decimal("0.30")
    confidence = max(Decimal("0.10"), min(Decimal("0.99"), confidence))

    # Deduplicate entity_refs
    seen = set()
    unique_refs = []
    for ref in all_entity_refs:
        key = (ref.get('type'), ref.get('id'))
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)

    return {
        'agent_type': agent_type,
        'conclusion': ' '.join(conclusion_parts) if conclusion_parts else 'No significant findings from available data.',
        'confidence': str(confidence.quantize(Decimal("0.01"))),
        'evidence': evidence,
        'reasoning': ' '.join(reasoning_parts) if reasoning_parts else 'Insufficient data for detailed analysis.',
        'recommended_actions': recommendations,
        'pending_approvals': pending_approvals,
        'entity_refs': unique_refs,
        'tools_called': list(tool_results.keys()),
        'system_prompt': system_prompt,
    }


# ── Per-tool processors ─────────────────────────────────────────────

def _process_cashflow(r, conc, reas, recs):
    conc.append(
        f"Current cash position: {r['current_balance']}. "
        f"30-day: {r['position_30d']}, 60-day: {r['position_60d']}, "
        f"90-day: {r['position_90d']}."
    )
    if r.get('pressure_day'):
        conc.append(f"Cash-flow pressure expected in {r['pressure_day']} days.")
        reas.append(r.get('risk_explanation', ''))
        recs.append("Review delayed receivables and upcoming payables to mitigate pressure.")
    else:
        reas.append("No cash-flow pressure detected in the 90-day forecast window.")

    reas.append(
        f"Average collection: {r['avg_collection_days']}d, "
        f"average payment: {r['avg_payment_days']}d."
    )


def _process_risk(r, conc, reas, recs):
    total = r.get('total', 0)
    conc.append(f"{total} open risk signal(s).")
    by_sev = r.get('by_severity', {})
    if by_sev.get('critical', 0) or by_sev.get('high', 0):
        crit = by_sev.get('critical', 0)
        high = by_sev.get('high', 0)
        conc.append(f"{crit} critical, {high} high severity.")
        recs.append(f"Address {crit + high} critical/high risk signals immediately.")
    reas.append(f"Risk breakdown by category: {r.get('by_category', {})}.")


def _process_recon(r, conc, reas, recs):
    if r.get('status') == 'no_runs':
        conc.append("No reconciliation has been run yet.")
        recs.append("Run the reconciliation engine to identify mismatches.")
        return
    conc.append(
        f"Last reconciliation: {r['exact_matches']} exact, "
        f"{r['fuzzy_matches']} fuzzy matches, "
        f"{r['pending_exceptions']} pending exceptions."
    )
    if r.get('pending_exceptions', 0) > 0:
        recs.append(f"Review {r['pending_exceptions']} pending reconciliation exceptions.")
    reas.append(f"Reconciliation run status: {r['status']}, unmatched: {r.get('unmatched', 0)}.")


def _process_scores(tool_name, r, conc, reas, recs):
    entity = 'vendor' if 'vendor' in tool_name else 'customer'
    count = r.get('count', 0)
    results = r.get('results', [])
    if not results:
        conc.append(f"No {entity} scores available.")
        return
    low_scores = [s for s in results if Decimal(s['overall_score']) < Decimal('50')]
    conc.append(f"{count} {entity}(s) scored. {len(low_scores)} below 50/100.")
    if low_scores:
        names = ', '.join(s[f'{entity}_name'] for s in low_scores[:3])
        recs.append(f"Review low-scoring {entity}s: {names}.")
    reas.append(
        f"Top {entity}: {results[0][f'{entity}_name']} ({results[0]['overall_score']}), "
        f"lowest shown: {results[-1][f'{entity}_name']} ({results[-1]['overall_score']})."
    )


def _process_overdue(r, conc, reas, recs):
    conc.append(f"₹{r['total_overdue']} overdue across {r['count']} invoice(s).")
    if r['count'] > 0:
        top = r['items'][0]
        reas.append(
            f"Largest overdue: {top['customer']} — ₹{top['amount']} "
            f"({top['days_overdue']}d overdue)."
        )
        recs.append("Send payment reminders for top overdue invoices.")


def _process_payables(r, conc, reas, recs):
    conc.append(f"₹{r['total_due']} in payables due ({r['count']} item(s)).")
    if r['count'] > 0:
        next_due = r['items'][0]
        reas.append(
            f"Next due: {next_due['vendor']} — ₹{next_due['amount']} "
            f"in {next_due['days_until_due']}d."
        )


def _process_audit(r, conc, reas):
    entries = r.get('entries', [])
    conc.append(f"{len(entries)} recent audit log entries retrieved.")
    if entries:
        latest = entries[0]
        reas.append(
            f"Latest: {latest['action']} on {latest['resource_type']}:{latest['resource_id']} "
            f"by {latest['user']} at {latest['timestamp']}."
        )


def _process_exceptions(r, conc, reas, recs):
    count = r.get('count', 0)
    conc.append(f"{count} unresolved reconciliation exception(s).")
    items = r.get('items', [])
    if items:
        top = items[0]
        reas.append(
            f"Top exception: {top['mismatch_cause']} — {top['reason']} "
            f"(confidence: {top['confidence']})."
        )
        recs.append(f"Review {count} reconciliation exceptions starting with highest-confidence items.")


def _process_expenses(r, conc, reas, recs):
    conc.append(
        f"₹{r['total_expenses']} in expenses over the last {r['period_days']} days "
        f"({r['count']} transaction(s))."
    )
    items = r.get('items', [])
    if items:
        top = items[0]
        reas.append(
            f"Largest expense: ₹{top['amount']} to {top['vendor'] or 'Unknown'} "
            f"(ref: {top['reference'] or top['id']})."
        )
        if len(items) > 1:
            second = items[1]
            reas.append(
                f"Second largest: ₹{second['amount']} to {second['vendor'] or 'Unknown'}."
            )


def _process_customers_owing(r, conc, reas, recs):
    conc.append(
        f"₹{r['grand_total_owed']} owed by {r['count']} customer(s)."
    )
    items = r.get('items', [])
    if items:
        top = items[0]
        reas.append(
            f"Largest debtor: {top['customer_name']} owes ₹{top['total_owed']}."
        )
        if r['count'] > 3:
            recs.append("Focus collection efforts on top 3 debtors.")


def _process_profit(r, conc, reas, recs):
    conc.append(
        f"Current period profit: ₹{r['current_profit']} "
        f"(revenue ₹{r['current_revenue']}, expenses ₹{r['current_expenses']}). "
        f"Prior period profit: ₹{r['prior_profit']}."
    )
    change = Decimal(r['profit_change'])
    if change < 0:
        reas.append(
            f"Profit decreased by ₹{abs(change)} compared to the prior {r['period_days']}-day period."
        )
        contributors = r.get('top_expense_contributors', [])
        if contributors:
            names = [
                f"{c.get('vendor__name', 'Unknown')} (₹{c['amount']})"
                for c in contributors[:3]
            ]
            reas.append(f"Top expense contributors: {', '.join(names)}.")
        recs.append("Review top expense categories for cost reduction opportunities.")
    elif change > 0:
        reas.append(f"Profit increased by ₹{change}.")
    else:
        reas.append("Profit is flat compared to the prior period.")

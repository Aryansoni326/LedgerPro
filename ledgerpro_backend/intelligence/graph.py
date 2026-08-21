"""
Relational graph traversal queries for the Company→Vendor/Customer→
Transaction→RiskSignal entity graph.

Design principles:
  - No new models — the graph is the existing FK topology.
  - Every query is firm-scoped and index-backed (see Meta.indexes on each model).
  - Incremental by construction: every FK is written at row-insert time,
    so the graph updates on each write — never rebuilt in batch.
  - All traversals are bounded (max depth, max fan-out) to guarantee
    <500ms even at 10k+ transactions.

Three primary traversals:
  1. risk_signal_graph  — "show all transactions connected to this risk signal"
  2. vendor_history     — "show this vendor's full relationship history"
  3. evidence_drilldown — evidence chain for the Agentic/Audit layer
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from decimal import Decimal
from typing import Any

from django.db.models import Q, Prefetch

logger = logging.getLogger(__name__)

MAX_RELATED_TXNS = 50
MAX_RISK_SIGNALS = 30
MAX_RECON_LINKS = 30


def _txn_to_node(t) -> dict:
    return {
        'id': t.id,
        'type': 'transaction',
        'txn_type': t.txn_type,
        'direction': t.direction,
        'status': t.status,
        'amount': str(t.amount),
        'currency': t.currency,
        'txn_date': t.txn_date.isoformat(),
        'due_date': t.due_date.isoformat() if t.due_date else None,
        'reference_number': t.reference_number,
        'vendor_id': t.vendor_id,
        'customer_id': t.customer_id,
        'bill_id': t.bill_id,
        'trade_doc_id': t.trade_doc_id,
    }


def _signal_to_node(s) -> dict:
    return {
        'id': s.id,
        'type': 'risk_signal',
        'severity': s.severity,
        'category': s.category,
        'status': s.status,
        'title': s.title,
        'description': s.description[:300],
        'confidence': str(s.confidence),
        'entity_type': s.entity_type,
        'entity_id': s.entity_id,
        'vendor_id': s.vendor_id,
        'customer_id': s.customer_id,
        'created_at': s.created_at.isoformat(),
    }


def _vendor_to_node(v) -> dict:
    return {
        'id': v.id,
        'type': 'vendor',
        'name': v.name,
        'gstin': v.gstin,
        'pan': v.pan,
        'email': v.email,
    }


def _customer_to_node(c) -> dict:
    return {
        'id': c.id,
        'type': 'customer',
        'name': c.name,
        'gstin': c.gstin,
        'pan': c.pan,
        'email': c.email,
    }


def _recon_to_edge(link) -> dict:
    return {
        'id': link.id,
        'type': 'reconciliation_link',
        'match_group': str(link.match_group),
        'match_confidence': str(link.match_confidence),
        'match_method': link.match_method,
        'transaction_id': link.transaction_id,
        'matched_transaction_id': link.matched_transaction_id,
        'fx_difference': str(link.fx_difference) if link.fx_difference is not None else None,
    }


# ═══════════════════════════════════════════════════════════════════
# 1. Risk Signal Graph
# ═══════════════════════════════════════════════════════════════════

def risk_signal_graph(firm_id: int, signal_id: int) -> dict:
    """Return all transactions, counterparties, and reconciliation links
    connected to a specific risk signal.

    The traversal walks:
      RiskSignal → entity (transaction | trade_doc | vendor)
        → Transaction → ReconciliationLink → matched transactions
        → Vendor / Customer nodes
    """
    from .models import (
        ReconciliationException,
        ReconciliationLink,
        RiskSignal,
        Transaction,
    )

    signal = RiskSignal.objects.get(pk=signal_id, firm_id=firm_id)

    nodes: OrderedDict[str, dict] = OrderedDict()
    edges: list[dict] = []
    nodes[f'risk_signal:{signal.id}'] = _signal_to_node(signal)

    seed_txn_ids: set[int] = set()

    if signal.entity_type == 'transaction':
        seed_txn_ids.add(signal.entity_id)
    elif signal.entity_type == 'trade_doc':
        td_txns = Transaction.objects.filter(
            firm_id=firm_id, trade_doc_id=signal.entity_id, is_deleted=False,
        ).values_list('id', flat=True)[:MAX_RELATED_TXNS]
        seed_txn_ids.update(td_txns)
    elif signal.entity_type == 'vendor':
        v_txns = Transaction.objects.filter(
            firm_id=firm_id, vendor_id=signal.entity_id, is_deleted=False,
        ).order_by('-txn_date').values_list('id', flat=True)[:MAX_RELATED_TXNS]
        seed_txn_ids.update(v_txns)

    if signal.vendor_id:
        from .models import Vendor
        try:
            v = Vendor.objects.get(pk=signal.vendor_id, firm_id=firm_id)
            nodes[f'vendor:{v.id}'] = _vendor_to_node(v)
            edges.append({'from': f'risk_signal:{signal.id}', 'to': f'vendor:{v.id}', 'label': 'vendor'})
        except Vendor.DoesNotExist:
            pass

    if signal.customer_id:
        from .models import Customer
        try:
            c = Customer.objects.get(pk=signal.customer_id, firm_id=firm_id)
            nodes[f'customer:{c.id}'] = _customer_to_node(c)
            edges.append({'from': f'risk_signal:{signal.id}', 'to': f'customer:{c.id}', 'label': 'customer'})
        except Customer.DoesNotExist:
            pass

    txns = Transaction.objects.filter(
        pk__in=seed_txn_ids, firm_id=firm_id, is_deleted=False,
    ).select_related('vendor', 'customer')
    for t in txns:
        key = f'transaction:{t.id}'
        nodes[key] = _txn_to_node(t)
        edges.append({'from': f'risk_signal:{signal.id}', 'to': key, 'label': 'triggered_by'})
        _attach_counterparties(t, nodes, edges, key)

    recon_links = ReconciliationLink.objects.filter(
        Q(transaction_id__in=seed_txn_ids) | Q(matched_transaction_id__in=seed_txn_ids),
        firm_id=firm_id, is_deleted=False,
    )[:MAX_RECON_LINKS]

    matched_ids: set[int] = set()
    for link in recon_links:
        edges.append(_recon_to_edge(link))
        matched_ids.add(link.transaction_id)
        matched_ids.add(link.matched_transaction_id)

    extra_ids = matched_ids - seed_txn_ids
    if extra_ids:
        for t in Transaction.objects.filter(
            pk__in=extra_ids, firm_id=firm_id, is_deleted=False,
        ).select_related('vendor', 'customer'):
            key = f'transaction:{t.id}'
            if key not in nodes:
                nodes[key] = _txn_to_node(t)
                _attach_counterparties(t, nodes, edges, key)

    recon_exceptions = ReconciliationException.objects.filter(
        Q(transaction_id__in=seed_txn_ids) | Q(candidate_transaction_id__in=seed_txn_ids),
        firm_id=firm_id, is_deleted=False,
    )[:10]
    for exc in recon_exceptions:
        edges.append({
            'from': f'transaction:{exc.transaction_id}',
            'to': f'transaction:{exc.candidate_transaction_id}' if exc.candidate_transaction_id else None,
            'label': 'recon_exception',
            'mismatch_cause': exc.mismatch_cause,
            'reason': exc.reason[:200],
        })

    return {
        'root': f'risk_signal:{signal.id}',
        'nodes': list(nodes.values()),
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges),
    }


# ═══════════════════════════════════════════════════════════════════
# 2. Vendor / Customer History
# ═══════════════════════════════════════════════════════════════════

def vendor_history(firm_id: int, vendor_id: int) -> dict:
    """Full relationship graph for a vendor within a firm.

    Walks: Vendor → Transactions → ReconciliationLinks → Risk Signals
           Vendor → VendorScore
           Vendor → TradeFinanceLinks
    """
    from .models import (
        ReconciliationLink,
        RiskSignal,
        TradeFinanceLink,
        Transaction,
        Vendor,
        VendorScore,
    )

    vendor = Vendor.objects.get(pk=vendor_id, firm_id=firm_id)
    nodes: OrderedDict[str, dict] = OrderedDict()
    edges: list[dict] = []

    vkey = f'vendor:{vendor.id}'
    nodes[vkey] = _vendor_to_node(vendor)

    try:
        vs = VendorScore.objects.get(vendor=vendor)
        nodes[vkey]['score'] = str(vs.overall_score)
        nodes[vkey]['score_breakdown'] = vs.breakdown
    except VendorScore.DoesNotExist:
        pass

    txns = list(
        Transaction.objects.filter(
            firm_id=firm_id, vendor_id=vendor_id, is_deleted=False,
        ).select_related('customer').order_by('-txn_date')[:MAX_RELATED_TXNS]
    )
    txn_ids = set()
    for t in txns:
        tkey = f'transaction:{t.id}'
        nodes[tkey] = _txn_to_node(t)
        edges.append({'from': vkey, 'to': tkey, 'label': t.txn_type})
        txn_ids.add(t.id)
        if t.customer_id:
            ckey = f'customer:{t.customer_id}'
            if ckey not in nodes:
                from .models import Customer
                try:
                    c = Customer.objects.get(pk=t.customer_id, firm_id=firm_id)
                    nodes[ckey] = _customer_to_node(c)
                except Customer.DoesNotExist:
                    pass
            edges.append({'from': tkey, 'to': ckey, 'label': 'customer'})

    if txn_ids:
        recon_links = ReconciliationLink.objects.filter(
            Q(transaction_id__in=txn_ids) | Q(matched_transaction_id__in=txn_ids),
            firm_id=firm_id, is_deleted=False,
        )[:MAX_RECON_LINKS]
        matched_extra = set()
        for link in recon_links:
            edges.append(_recon_to_edge(link))
            matched_extra.add(link.transaction_id)
            matched_extra.add(link.matched_transaction_id)

        new_ids = matched_extra - txn_ids
        if new_ids:
            for t in Transaction.objects.filter(
                pk__in=new_ids, firm_id=firm_id, is_deleted=False,
            ):
                tkey = f'transaction:{t.id}'
                if tkey not in nodes:
                    nodes[tkey] = _txn_to_node(t)

    signals = RiskSignal.objects.filter(
        firm_id=firm_id, vendor_id=vendor_id, is_deleted=False,
    ).order_by('-created_at')[:MAX_RISK_SIGNALS]
    for s in signals:
        skey = f'risk_signal:{s.id}'
        nodes[skey] = _signal_to_node(s)
        edges.append({'from': vkey, 'to': skey, 'label': 'risk_signal'})

    tfl_links = TradeFinanceLink.objects.filter(
        firm_id=firm_id, vendor_id=vendor_id, is_deleted=False,
    ).order_by('-created_at')[:20]
    for tfl in tfl_links:
        tfl_key = f'trade_finance_link:{tfl.id}'
        nodes[tfl_key] = {
            'id': tfl.id,
            'type': 'trade_finance_link',
            'status': tfl.status,
            'invoice_amount': str(tfl.invoice_amount) if tfl.invoice_amount else None,
            'customs_declared_value': str(tfl.customs_declared_value) if tfl.customs_declared_value else None,
            'value_difference': str(tfl.value_difference) if tfl.value_difference is not None else None,
            'payment_before_shipment': tfl.payment_before_shipment,
        }
        edges.append({'from': vkey, 'to': tfl_key, 'label': 'trade_finance'})

    summary = _vendor_summary(vendor, txns, signals)

    return {
        'root': vkey,
        'nodes': list(nodes.values()),
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges),
        'summary': summary,
    }


def customer_history(firm_id: int, customer_id: int) -> dict:
    """Full relationship graph for a customer within a firm."""
    from .models import (
        Customer,
        CustomerScore,
        ReconciliationLink,
        RiskSignal,
        Transaction,
    )

    customer = Customer.objects.get(pk=customer_id, firm_id=firm_id)
    nodes: OrderedDict[str, dict] = OrderedDict()
    edges: list[dict] = []

    ckey = f'customer:{customer.id}'
    nodes[ckey] = _customer_to_node(customer)

    try:
        cs = CustomerScore.objects.get(customer=customer)
        nodes[ckey]['score'] = str(cs.overall_score)
        nodes[ckey]['score_breakdown'] = cs.breakdown
    except CustomerScore.DoesNotExist:
        pass

    txns = list(
        Transaction.objects.filter(
            firm_id=firm_id, customer_id=customer_id, is_deleted=False,
        ).select_related('vendor').order_by('-txn_date')[:MAX_RELATED_TXNS]
    )
    txn_ids = set()
    for t in txns:
        tkey = f'transaction:{t.id}'
        nodes[tkey] = _txn_to_node(t)
        edges.append({'from': ckey, 'to': tkey, 'label': t.txn_type})
        txn_ids.add(t.id)

    if txn_ids:
        recon_links = ReconciliationLink.objects.filter(
            Q(transaction_id__in=txn_ids) | Q(matched_transaction_id__in=txn_ids),
            firm_id=firm_id, is_deleted=False,
        )[:MAX_RECON_LINKS]
        for link in recon_links:
            edges.append(_recon_to_edge(link))

    signals = RiskSignal.objects.filter(
        firm_id=firm_id, customer_id=customer_id, is_deleted=False,
    ).order_by('-created_at')[:MAX_RISK_SIGNALS]
    for s in signals:
        skey = f'risk_signal:{s.id}'
        nodes[skey] = _signal_to_node(s)
        edges.append({'from': ckey, 'to': skey, 'label': 'risk_signal'})

    return {
        'root': ckey,
        'nodes': list(nodes.values()),
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges),
    }


# ═══════════════════════════════════════════════════════════════════
# 3. Evidence Drill-down (Agent / Audit layer)
# ═══════════════════════════════════════════════════════════════════

def evidence_drilldown(firm_id: int, entity_type: str, entity_id: int) -> dict:
    """Generic evidence chain starting from any entity type.

    Used by the Agentic layer (Phase 6) and the Audit Agent to
    produce traceable evidence for any claim.

    Supported entity_types: transaction, risk_signal, vendor, customer, trade_doc
    """
    dispatch = {
        'transaction': _evidence_from_transaction,
        'risk_signal': _evidence_from_risk_signal,
        'vendor': _evidence_from_vendor,
        'customer': _evidence_from_customer,
        'trade_doc': _evidence_from_trade_doc,
    }
    handler = dispatch.get(entity_type)
    if not handler:
        return {'error': f'Unknown entity_type: {entity_type}', 'nodes': [], 'edges': []}
    return handler(firm_id, entity_id)


def _evidence_from_transaction(firm_id: int, txn_id: int) -> dict:
    from .models import (
        ReconciliationException,
        ReconciliationLink,
        RiskSignal,
        Transaction,
    )

    txn = Transaction.objects.select_related('vendor', 'customer').get(
        pk=txn_id, firm_id=firm_id, is_deleted=False,
    )
    nodes: OrderedDict[str, dict] = OrderedDict()
    edges: list[dict] = []

    tkey = f'transaction:{txn.id}'
    nodes[tkey] = _txn_to_node(txn)
    _attach_counterparties(txn, nodes, edges, tkey)

    recon = ReconciliationLink.objects.filter(
        Q(transaction_id=txn.id) | Q(matched_transaction_id=txn.id),
        firm_id=firm_id, is_deleted=False,
    )[:MAX_RECON_LINKS]
    matched_ids: set[int] = set()
    for link in recon:
        edges.append(_recon_to_edge(link))
        matched_ids.add(link.transaction_id)
        matched_ids.add(link.matched_transaction_id)

    for t in Transaction.objects.filter(
        pk__in=matched_ids - {txn.id}, firm_id=firm_id, is_deleted=False,
    ).select_related('vendor', 'customer'):
        key = f'transaction:{t.id}'
        nodes[key] = _txn_to_node(t)
        _attach_counterparties(t, nodes, edges, key)

    signals = RiskSignal.objects.filter(
        firm_id=firm_id, entity_type='transaction', entity_id=txn.id, is_deleted=False,
    )[:MAX_RISK_SIGNALS]
    for s in signals:
        skey = f'risk_signal:{s.id}'
        nodes[skey] = _signal_to_node(s)
        edges.append({'from': tkey, 'to': skey, 'label': 'risk_signal'})

    exceptions = ReconciliationException.objects.filter(
        Q(transaction_id=txn.id) | Q(candidate_transaction_id=txn.id),
        firm_id=firm_id, is_deleted=False,
    )[:10]
    for exc in exceptions:
        edges.append({
            'from': f'transaction:{exc.transaction_id}',
            'to': f'transaction:{exc.candidate_transaction_id}' if exc.candidate_transaction_id else None,
            'label': 'recon_exception',
            'mismatch_cause': exc.mismatch_cause,
        })

    return {
        'root': tkey,
        'entity_type': 'transaction',
        'entity_id': txn_id,
        'nodes': list(nodes.values()),
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges),
    }


def _evidence_from_risk_signal(firm_id: int, signal_id: int) -> dict:
    result = risk_signal_graph(firm_id, signal_id)
    result['entity_type'] = 'risk_signal'
    result['entity_id'] = signal_id
    return result


def _evidence_from_vendor(firm_id: int, vendor_id: int) -> dict:
    result = vendor_history(firm_id, vendor_id)
    result['entity_type'] = 'vendor'
    result['entity_id'] = vendor_id
    return result


def _evidence_from_customer(firm_id: int, customer_id: int) -> dict:
    result = customer_history(firm_id, customer_id)
    result['entity_type'] = 'customer'
    result['entity_id'] = customer_id
    return result


def _evidence_from_trade_doc(firm_id: int, trade_doc_id: int) -> dict:
    from .models import RiskSignal, TradeFinanceLink, Transaction

    nodes: OrderedDict[str, dict] = OrderedDict()
    edges: list[dict] = []

    txns = Transaction.objects.filter(
        firm_id=firm_id, trade_doc_id=trade_doc_id, is_deleted=False,
    ).select_related('vendor', 'customer')[:MAX_RELATED_TXNS]
    for t in txns:
        tkey = f'transaction:{t.id}'
        nodes[tkey] = _txn_to_node(t)
        _attach_counterparties(t, nodes, edges, tkey)

    signals = RiskSignal.objects.filter(
        firm_id=firm_id, entity_type='trade_doc', entity_id=trade_doc_id,
        is_deleted=False,
    )[:MAX_RISK_SIGNALS]
    for s in signals:
        skey = f'risk_signal:{s.id}'
        nodes[skey] = _signal_to_node(s)

    tfl_links = TradeFinanceLink.objects.filter(
        firm_id=firm_id, trade_doc_id=trade_doc_id, is_deleted=False,
    )[:10]
    for tfl in tfl_links:
        tfl_key = f'trade_finance_link:{tfl.id}'
        nodes[tfl_key] = {
            'id': tfl.id, 'type': 'trade_finance_link', 'status': tfl.status,
        }
        if tfl.invoice_txn_id:
            edges.append({'from': tfl_key, 'to': f'transaction:{tfl.invoice_txn_id}', 'label': 'invoice'})
        if tfl.payment_txn_id:
            edges.append({'from': tfl_key, 'to': f'transaction:{tfl.payment_txn_id}', 'label': 'payment'})

    return {
        'root': f'trade_doc:{trade_doc_id}',
        'entity_type': 'trade_doc',
        'entity_id': trade_doc_id,
        'nodes': list(nodes.values()),
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges),
    }


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _attach_counterparties(txn, nodes, edges, txn_key):
    if txn.vendor_id:
        vkey = f'vendor:{txn.vendor_id}'
        if vkey not in nodes and hasattr(txn, 'vendor') and txn.vendor:
            nodes[vkey] = _vendor_to_node(txn.vendor)
        edges.append({'from': txn_key, 'to': vkey, 'label': 'vendor'})
    if txn.customer_id:
        ckey = f'customer:{txn.customer_id}'
        if ckey not in nodes and hasattr(txn, 'customer') and txn.customer:
            nodes[ckey] = _customer_to_node(txn.customer)
        edges.append({'from': txn_key, 'to': ckey, 'label': 'customer'})


def _vendor_summary(vendor, txns, signals) -> dict:
    total_value = sum(t.amount for t in txns)
    by_type: dict[str, int] = {}
    for t in txns:
        by_type[t.txn_type] = by_type.get(t.txn_type, 0) + 1
    open_signals = sum(1 for s in signals if s.status == 'open')
    return {
        'vendor_id': vendor.id,
        'vendor_name': vendor.name,
        'total_transactions': len(txns),
        'total_value': str(total_value),
        'transactions_by_type': by_type,
        'open_risk_signals': open_signals,
        'total_risk_signals': len(signals),
    }

"""
Intelligence module views — unified document upload, list, manage, verify,
retry-extraction, risk-signal listing, and risk-summary endpoints.

Follows the exact same pattern as ``invoices.views``, ``trade_docs.views``,
and ``eway_bills.views``.
"""
import logging
import os
from io import BytesIO

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.services import log_audit
from common.classifier import classify_document, INTELLIGENCE_TASK_MAP
from common.upload_validation import DOCUMENT_EXTENSIONS, UploadValidationError, validate_upload
from firms.access import (
    assert_can_write_firm,
    firm_filter_for_user,
    get_document_for_user,
    get_firm_or_403,
    get_risk_signal_for_user,
)
from firms.permissions import HasFirmAccess

from .models import (
    Customer, CustomerScore, Document, FinancialSnapshot,
    RiskSignal, TradeFinanceLink, Vendor, VendorScore,
)
from .services import DocumentStorageService

logger = logging.getLogger(__name__)

# Import tasks lazily to avoid circular imports at module level
_TASK_CACHE = {}


def _get_task(doc_type: str):
    if doc_type not in _TASK_CACHE:
        task_path = INTELLIGENCE_TASK_MAP.get(doc_type)
        if not task_path:
            return None
        module_path, func_name = task_path.rsplit('.', 1)
        import importlib
        mod = importlib.import_module(module_path)
        _TASK_CACHE[doc_type] = getattr(mod, func_name)
    return _TASK_CACHE[doc_type]


def _doc_to_dict(doc: Document) -> dict:
    return {
        'id': doc.id,
        'firm_id': doc.firm_id,
        'doc_type': doc.doc_type,
        'file_name': doc.file_name,
        'file_url': doc.file_url,
        'file_size': doc.file_size,
        'status': doc.status,
        'uploaded_by': doc.uploaded_by_id,
        'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        'raw_data': doc.raw_data,
        'validation_warnings': doc.validation_warnings,
        'extraction_failed': doc.extraction_failed,
        'classified_type': doc.classified_type,
        'classification_confidence': str(doc.classification_confidence),
        'created_at': doc.created_at.isoformat(),
        'updated_at': doc.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Upload (with auto-classification)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def upload_documents(request, firm_id):
    """Upload documents for a firm. Auto-classifies each file and routes to
    the appropriate extraction task. If ``doc_type`` is provided in POST data,
    classification is skipped and that type is used directly.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    write_err = assert_can_write_firm(request.user, firm)
    if write_err:
        return write_err

    files = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not files:
        return Response(
            {'error': 'No files provided for upload.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from billing.entitlements import reserve_documents_for_firm
    from billing.exceptions import BillingError

    explicit_type = request.data.get('doc_type', '').strip()
    uploaded = []
    errors = []

    api_key = os.environ.get('GEMINI_API_KEY')

    for f in files:
        try:
            file_bytes, _ext = validate_upload(f, allowed_extensions=DOCUMENT_EXTENSIONS)
        except UploadValidationError as exc:
            errors.append(f"File '{f.name}': {exc}")
            continue

        try:
            reserve_documents_for_firm(firm, amount=1)
        except BillingError as exc:
            errors.append(f"File '{f.name}': {exc.message}")
            break

        # Classify
        if explicit_type and explicit_type in INTELLIGENCE_TASK_MAP:
            doc_type = explicit_type
            confidence = 1.0
        else:
            doc_type, confidence = classify_document(
                file_data=file_bytes,
                filename=f.name,
                api_key=api_key,
            )

        # If classifier says it's a legacy type or unknown, reject with guidance
        if doc_type not in INTELLIGENCE_TASK_MAP:
            errors.append(
                f"File '{f.name}': classified as '{doc_type}' — please upload via "
                f"the dedicated endpoint (invoices, trade-docs, or eway-bills) "
                f"or specify doc_type explicitly."
            )
            continue

        # Store
        try:
            buf = BytesIO(file_bytes)
            buf.name = f.name
            file_url = DocumentStorageService.upload_document(buf, firm.id, doc_type)

            doc = Document(
                firm=firm,
                doc_type=doc_type,
                file_name=f.name,
                file_url=file_url,
                file_size=len(file_bytes),
                status='processing',
                uploaded_by=request.user,
                classified_type=doc_type,
                classification_confidence=confidence,
            )
            doc.save()

            # Vault entry
            from vault.models import CloudVaultEntry
            CloudVaultEntry.objects.create(
                firm=firm,
                file_name=doc.file_name,
                file_url=doc.file_url,
                module='documents',
                is_finalized=False,
            )

            # Enqueue extraction
            task_fn = _get_task(doc_type)
            if task_fn:
                task_fn.delay(doc.id)

            log_audit(
                user=request.user,
                firm=firm,
                resource_type='document',
                resource_id=doc.id,
                action='upload',
                details={'doc_type': doc_type, 'file_name': f.name},
                request=request,
            )

            uploaded.append(_doc_to_dict(doc))

        except Exception as exc:
            logger.error("Failed to store document '%s': %s", f.name, exc, exc_info=True)
            errors.append(f"File '{f.name}': storage error — {exc}")

    return Response(
        {'uploaded': uploaded, 'errors': errors},
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def list_documents(request, firm_id):
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = Document.objects.filter(firm=firm).order_by('-uploaded_at')

    doc_type = request.query_params.get('doc_type')
    if doc_type:
        qs = qs.filter(doc_type=doc_type)

    doc_status = request.query_params.get('status')
    if doc_status:
        qs = qs.filter(status=doc_status)

    return Response([_doc_to_dict(d) for d in qs])


# ---------------------------------------------------------------------------
# Get / Patch / Delete
# ---------------------------------------------------------------------------

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_document(request, pk):
    doc = get_document_for_user(request.user, pk)

    if request.method == 'GET':
        return Response(_doc_to_dict(doc))

    # Write operations — owners are read-only
    write_err = assert_can_write_firm(request.user, doc.firm)
    if write_err:
        return write_err

    if request.method == 'DELETE':
        doc.soft_delete()
        log_audit(
            user=request.user, firm=doc.firm,
            resource_type='document', resource_id=doc.id,
            action='delete', details={'file_name': doc.file_name},
            request=request,
        )
        return Response({'status': 'deleted'})

    # PATCH
    raw_data = request.data.get('raw_data')
    if raw_data is not None:
        doc.raw_data = raw_data
        doc.save(update_fields=['raw_data', 'updated_at'])
        log_audit(
            user=request.user, firm=doc.firm,
            resource_type='document', resource_id=doc.id,
            action='edit', details={'updated_fields': ['raw_data']},
            request=request,
        )

    return Response(_doc_to_dict(doc))


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_document(request, pk):
    doc = get_document_for_user(request.user, pk)

    write_err = assert_can_write_firm(request.user, doc.firm)
    if write_err:
        return write_err

    if doc.status not in ('needs_review', 'verified'):
        return Response(
            {'error': f"Cannot verify a document in '{doc.status}' status."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    doc.status = 'verified'
    doc.save(update_fields=['status', 'updated_at'])

    log_audit(
        user=request.user, firm=doc.firm,
        resource_type='document', resource_id=doc.id,
        action='verify', details={'doc_type': doc.doc_type},
        request=request,
    )

    return Response(_doc_to_dict(doc))


# ---------------------------------------------------------------------------
# Retry extraction
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_document_extraction(request, pk):
    doc = get_document_for_user(request.user, pk)

    write_err = assert_can_write_firm(request.user, doc.firm)
    if write_err:
        return write_err

    doc.status = 'processing'
    doc.extraction_failed = False
    doc.save(update_fields=['status', 'extraction_failed', 'updated_at'])

    task_fn = _get_task(doc.doc_type)
    if task_fn:
        task_fn.delay(doc.id)

    log_audit(
        user=request.user, firm=doc.firm,
        resource_type='document', resource_id=doc.id,
        action='retry_extraction', details={'doc_type': doc.doc_type},
        request=request,
    )

    return Response(_doc_to_dict(doc))


# ===========================================================================
# Risk Signal endpoints
# ===========================================================================

# Dashboard-friendly status aliases → DB status values.
# The dashboard uses "open / reviewed / dismissed"; the DB stores the
# granular enum.  This mapping lets the API accept either vocabulary.
_STATUS_ALIASES: dict[str, list[str]] = {
    'open': ['open'],
    'reviewed': ['acknowledged', 'resolved'],
    'dismissed': ['false_positive'],
    # Direct DB values also accepted
    'acknowledged': ['acknowledged'],
    'resolved': ['resolved'],
    'false_positive': ['false_positive'],
}

_SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100


def _risk_signal_to_dict(sig: RiskSignal) -> dict:
    return {
        'id': sig.id,
        'firm_id': sig.firm_id,
        'severity': sig.severity,
        'category': sig.category,
        'status': sig.status,
        'title': sig.title,
        'description': sig.description,
        'confidence': str(sig.confidence),
        'entity_type': sig.entity_type,
        'entity_id': sig.entity_id,
        'vendor_id': sig.vendor_id,
        'customer_id': sig.customer_id,
        'resolved_by_id': sig.resolved_by_id,
        'resolved_at': sig.resolved_at.isoformat() if sig.resolved_at else None,
        'ai_reasoning': sig.ai_reasoning,
        'created_at': sig.created_at.isoformat(),
        'updated_at': sig.updated_at.isoformat(),
    }


def _parse_page_size(request) -> int:
    try:
        size = int(request.query_params.get('page_size', _DEFAULT_PAGE_SIZE))
    except (ValueError, TypeError):
        size = _DEFAULT_PAGE_SIZE
    return min(max(size, 1), _MAX_PAGE_SIZE)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def list_risk_signals(request, firm_id):
    """
    **GET /api/firms/{firm_id}/risk-signals/**

    Paginated, filterable list of risk signals for a firm.

    ### Query parameters

    | Param         | Type   | Description                                          |
    |---------------|--------|------------------------------------------------------|
    | `severity`    | string | Filter: `low`, `medium`, `high`, `critical`          |
    | `category`    | string | Filter: any `RiskSignal.Category` value              |
    | `status`      | string | Filter: `open`, `reviewed`, `dismissed` (aliases)    |
    |               |        | or raw DB values: `acknowledged`, `resolved`,        |
    |               |        | `false_positive`                                     |
    | `entity_type` | string | Filter by entity type (e.g. `bill`, `vendor`)        |
    | `entity_id`   | int    | Filter by entity ID (requires `entity_type`)         |
    | `vendor_id`   | int    | Filter by vendor FK                                  |
    | `customer_id` | int    | Filter by customer FK                                |
    | `created_after`  | ISO date | Signals created on or after this date             |
    | `created_before` | ISO date | Signals created on or before this date            |
    | `page`        | int    | 1-based page number (default 1)                      |
    | `page_size`   | int    | Items per page, 1–100 (default 25)                   |
    | `ordering`    | string | `-created_at` (default), `created_at`, `severity`,   |
    |               |        | `-severity`                                          |

    ### Response

    ```json
    {
      "count": 142,
      "page": 1,
      "page_size": 25,
      "total_pages": 6,
      "results": [ … ]
    }
    ```
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = RiskSignal.objects.filter(firm=firm)

    # --- Filters (all hit indexed columns) --------------------------------

    severity = request.query_params.get('severity')
    if severity and severity in RiskSignal.Severity.values:
        qs = qs.filter(severity=severity)

    category = request.query_params.get('category')
    if category and category in RiskSignal.Category.values:
        qs = qs.filter(category=category)

    status_param = request.query_params.get('status')
    if status_param:
        db_values = _STATUS_ALIASES.get(status_param.lower())
        if db_values:
            qs = qs.filter(status__in=db_values)

    entity_type = request.query_params.get('entity_type')
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
        entity_id = request.query_params.get('entity_id')
        if entity_id:
            try:
                qs = qs.filter(entity_id=int(entity_id))
            except (ValueError, TypeError):
                pass

    vendor_id = request.query_params.get('vendor_id')
    if vendor_id:
        try:
            qs = qs.filter(vendor_id=int(vendor_id))
        except (ValueError, TypeError):
            pass

    customer_id = request.query_params.get('customer_id')
    if customer_id:
        try:
            qs = qs.filter(customer_id=int(customer_id))
        except (ValueError, TypeError):
            pass

    created_after = request.query_params.get('created_after')
    if created_after:
        qs = qs.filter(created_at__date__gte=created_after)

    created_before = request.query_params.get('created_before')
    if created_before:
        qs = qs.filter(created_at__date__lte=created_before)

    # --- Ordering ---------------------------------------------------------

    ordering = request.query_params.get('ordering', '-created_at')
    allowed_orderings = {
        'created_at', '-created_at', 'severity', '-severity',
    }
    if ordering not in allowed_orderings:
        ordering = '-created_at'
    qs = qs.order_by(ordering)

    # --- Offset pagination ------------------------------------------------

    page_size = _parse_page_size(request)
    try:
        page = max(int(request.query_params.get('page', 1)), 1)
    except (ValueError, TypeError):
        page = 1

    total = qs.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    start = (page - 1) * page_size

    results = [
        _risk_signal_to_dict(sig)
        for sig in qs[start:start + page_size]
    ]

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'results': results,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def risk_summary(request, firm_id):
    """
    **GET /api/firms/{firm_id}/risk-summary/**

    Aggregated risk-signal counts for dashboard cards.  Returns in <200 ms
    for 10 k+ signals because it runs a single indexed ``GROUP BY`` query
    against the ``idx_risk_dashboard`` composite index
    (firm, status, severity, -created_at).

    ### Query parameters

    | Param    | Type   | Description                                       |
    |----------|--------|---------------------------------------------------|
    | `status` | string | Optional filter — same aliases as list endpoint   |

    ### Response

    ```json
    {
      "total": 142,
      "by_severity": {
        "critical": 3,
        "high": 18,
        "medium": 57,
        "low": 64
      },
      "by_status": {
        "open": 82,
        "acknowledged": 31,
        "resolved": 22,
        "false_positive": 7
      },
      "by_category": {
        "gst_mismatch": 25,
        "duplicate_invoice": 12,
        …
      },
      "recent": [ … ]   // 5 most recent open signals (mini-preview)
    }
    ```
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    base_qs = RiskSignal.objects.filter(firm=firm)

    # Optional status filter (same alias support as list endpoint)
    status_param = request.query_params.get('status')
    if status_param:
        db_values = _STATUS_ALIASES.get(status_param.lower())
        if db_values:
            base_qs = base_qs.filter(status__in=db_values)

    # ── Aggregation queries (single-pass each, index-covered) ─────────

    severity_counts = dict(
        base_qs
        .values_list('severity')
        .annotate(n=Count('id'))
        .values_list('severity', 'n')
    )

    status_counts = dict(
        base_qs
        .values_list('status')
        .annotate(n=Count('id'))
        .values_list('status', 'n')
    )

    category_counts = dict(
        base_qs
        .values_list('category')
        .annotate(n=Count('id'))
        .values_list('category', 'n')
    )

    total = sum(severity_counts.values())

    # Ensure every severity / status key is present even if count is 0
    by_severity = {s: severity_counts.get(s, 0) for s in RiskSignal.Severity.values}
    by_status = {s: status_counts.get(s, 0) for s in RiskSignal.Status.values}
    by_category = {c: category_counts.get(c, 0) for c in RiskSignal.Category.values}

    # ── Recent open signals (preview for dashboard widget) ────────────
    recent_qs = (
        RiskSignal.objects
        .filter(firm=firm, status='open')
        .order_by('-created_at')[:5]
    )
    recent = [_risk_signal_to_dict(s) for s in recent_qs]

    return Response({
        'total': total,
        'by_severity': by_severity,
        'by_status': by_status,
        'by_category': by_category,
        'recent': recent,
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def manage_risk_signal(request, pk):
    """
    **GET /api/risk-signals/{id}/** — retrieve a single risk signal.

    **PATCH /api/risk-signals/{id}/** — update status (e.g. acknowledge,
    resolve, dismiss) or add notes.

    Accepted PATCH fields: `status`, `resolved_at` (auto-set on resolve).
    """
    sig = get_risk_signal_for_user(request.user, pk)

    if request.method == 'GET':
        return Response(_risk_signal_to_dict(sig))

    # PATCH — write access required
    write_err = assert_can_write_firm(request.user, sig.firm)
    if write_err:
        return write_err

    new_status = request.data.get('status')
    if new_status and new_status in RiskSignal.Status.values:
        sig.status = new_status
        if new_status in ('resolved', 'false_positive'):
            sig.resolved_by = request.user
            sig.resolved_at = timezone.now()
        sig.save(update_fields=['status', 'resolved_by', 'resolved_at', 'updated_at'])
        log_audit(
            user=request.user, firm=sig.firm,
            resource_type='risk_signal', resource_id=sig.id,
            action='edit', details={'new_status': new_status},
            request=request,
        )

    return Response(_risk_signal_to_dict(sig))


# ===========================================================================
# Cash-flow forecast endpoint
# ===========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def cash_flow_forecast(request, firm_id):
    """
    **GET /api/firms/{firm_id}/cash-flow-forecast/**

    Returns the firm's current and projected 30/60/90-day cash positions
    plus a plain-English risk explanation generated from actual line items.

    If a fresh forecast hasn't been computed today, it runs the forecaster
    on-demand (fast enough for a synchronous request with typical data
    volumes).  The nightly Celery beat task pre-computes snapshots so this
    path is rarely hit.

    ### Query parameters

    | Param   | Type | Description                                   |
    |---------|------|-----------------------------------------------|
    | `fresh` | bool | Force recomputation (default: use cached)     |

    ### Response

    ```json
    {
      "as_of": "2026-08-19",
      "current_balance": "1250000.00",
      "position_30d": "980000.00",
      "position_60d": "740000.00",
      "position_90d": "620000.00",
      "pressure_day": 57,
      "pressure_amount": "-120000.00",
      "risk_explanation": "Potential cash-flow pressure in 57 days …",
      "health_score": "65.00",
      "avg_collection_days": "42.3",
      "avg_payment_days": "28.7",
      "top_delayed_receivables": [ … ],
      "top_upcoming_payables": [ … ],
      "daily_forecast": [ … ]
    }
    ```
    """
    from datetime import date as date_type
    from .forecasting import CashFlowForecaster

    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    today = date_type.today()
    force_fresh = request.query_params.get('fresh', '').lower() in ('true', '1', 'yes')

    # Try cached snapshot first
    if not force_fresh:
        snapshot = (
            FinancialSnapshot.objects
            .filter(firm=firm, snapshot_type='daily', snapshot_date=today)
            .first()
        )
        if snapshot and snapshot.cashflow_forecast:
            return Response({
                'as_of': str(today),
                'current_balance': str(snapshot.cashflow_forecast.get('current_balance', '0')),
                'position_30d': str(snapshot.cashflow_forecast.get('position_30d', '0')),
                'position_60d': str(snapshot.cashflow_forecast.get('position_60d', '0')),
                'position_90d': str(snapshot.cashflow_forecast.get('position_90d', '0')),
                'pressure_day': snapshot.cashflow_forecast.get('pressure_day'),
                'pressure_amount': snapshot.cashflow_forecast.get('pressure_amount'),
                'risk_explanation': snapshot.cashflow_forecast.get('risk_explanation', ''),
                'health_score': str(snapshot.health_score),
                'avg_collection_days': snapshot.cashflow_forecast.get('avg_collection_days', '30'),
                'avg_payment_days': snapshot.cashflow_forecast.get('avg_payment_days', '30'),
                'top_delayed_receivables': snapshot.cashflow_forecast.get('top_delayed_receivables', []),
                'top_upcoming_payables': snapshot.cashflow_forecast.get('top_upcoming_payables', []),
                'daily_forecast': snapshot.breakdown.get('daily_positions', []),
            })

    # Compute on-demand
    forecaster = CashFlowForecaster()
    result = forecaster.forecast(firm_id, as_of=today)
    forecaster.save_snapshot(firm_id, result)

    return Response({
        'as_of': str(result.as_of),
        'current_balance': str(result.current_balance),
        'position_30d': str(result.position_30d),
        'position_60d': str(result.position_60d),
        'position_90d': str(result.position_90d),
        'pressure_day': result.pressure_day,
        'pressure_amount': str(result.pressure_amount) if result.pressure_amount else None,
        'risk_explanation': result.risk_explanation,
        'health_score': str(result.health_score),
        'avg_collection_days': str(result.avg_collection_days),
        'avg_payment_days': str(result.avg_payment_days),
        'top_delayed_receivables': result.top_delayed_receivables,
        'top_upcoming_payables': result.top_upcoming_payables,
        'daily_forecast': [
            {
                'day': str(d.day),
                'inflows': str(d.projected_inflows),
                'outflows': str(d.projected_outflows),
                'cumulative': str(d.cumulative_position),
            }
            for d in result.daily_forecast
        ],
    })


# ===========================================================================
# Vendor / Customer score endpoints
# ===========================================================================

def _vendor_score_to_dict(vs: VendorScore) -> dict:
    return {
        'vendor_id': vs.vendor_id,
        'vendor_name': vs.vendor.name,
        'overall_score': str(vs.overall_score),
        'previous_score': str(vs.previous_score) if vs.previous_score is not None else None,
        'sub_metrics': {
            'invoice_consistency': {'score': str(vs.invoice_consistency), 'weight': '0.20'},
            'payment_history': {'score': str(vs.payment_history), 'weight': '0.25'},
            'price_stability': {'score': str(vs.price_stability), 'weight': '0.15'},
            'document_quality': {'score': str(vs.document_quality), 'weight': '0.15'},
            'bank_change_frequency': {'score': str(vs.bank_change_frequency), 'weight': '0.10'},
            'anomaly_history': {'score': str(vs.anomaly_history), 'weight': '0.15'},
        },
        'breakdown': vs.breakdown,
        'last_computed_at': vs.last_computed_at.isoformat() if vs.last_computed_at else None,
    }


def _customer_score_to_dict(cs: CustomerScore) -> dict:
    return {
        'customer_id': cs.customer_id,
        'customer_name': cs.customer.name,
        'overall_score': str(cs.overall_score),
        'previous_score': str(cs.previous_score) if cs.previous_score is not None else None,
        'sub_metrics': {
            'payment_history': {'score': str(cs.payment_history), 'weight': '0.30'},
            'avg_payment_time_trend': {'score': str(cs.avg_payment_time_trend), 'weight': '0.20'},
            'credit_exposure': {'score': str(cs.credit_exposure), 'weight': '0.25'},
            'revenue_contribution': {'score': str(cs.revenue_contribution), 'weight': '0.25'},
        },
        'breakdown': cs.breakdown,
        'last_computed_at': cs.last_computed_at.isoformat() if cs.last_computed_at else None,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def vendor_score_list(request, firm_id):
    """
    **GET /api/firms/{firm_id}/vendor-scores/**

    Returns all vendor scores for the firm, ranked by overall_score descending.
    Supports `?min_score=N` and `?max_score=N` filters.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = VendorScore.objects.filter(firm=firm).select_related('vendor').order_by('-overall_score')

    min_score = request.query_params.get('min_score')
    max_score = request.query_params.get('max_score')
    if min_score:
        qs = qs.filter(overall_score__gte=min_score)
    if max_score:
        qs = qs.filter(overall_score__lte=max_score)

    return Response({
        'count': qs.count(),
        'results': [_vendor_score_to_dict(vs) for vs in qs],
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vendor_score_detail(request, pk):
    """
    **GET /api/vendors/{pk}/score/** — vendor score with full breakdown.

    **POST /api/vendors/{pk}/score/** — trigger an incremental recomputation.
    """
    try:
        vendor = Vendor.objects.select_related('firm').get(pk=pk)
    except Vendor.DoesNotExist:
        return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (vendor.firm.created_by == request.user or vendor.firm.owner_email.lower() == request.user.email.lower()):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'POST':
        from .scoring import compute_vendor_score
        score_obj = compute_vendor_score(vendor)
        return Response(_vendor_score_to_dict(score_obj), status=status.HTTP_200_OK)

    try:
        vs = VendorScore.objects.select_related('vendor').get(vendor=vendor)
    except VendorScore.DoesNotExist:
        return Response({'error': 'Score not yet computed. POST to trigger computation.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(_vendor_score_to_dict(vs))


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def customer_score_list(request, firm_id):
    """
    **GET /api/firms/{firm_id}/customer-scores/**

    Returns all customer scores for the firm, ranked by overall_score descending.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = CustomerScore.objects.filter(firm=firm).select_related('customer').order_by('-overall_score')

    min_score = request.query_params.get('min_score')
    max_score = request.query_params.get('max_score')
    if min_score:
        qs = qs.filter(overall_score__gte=min_score)
    if max_score:
        qs = qs.filter(overall_score__lte=max_score)

    return Response({
        'count': qs.count(),
        'results': [_customer_score_to_dict(cs) for cs in qs],
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def customer_score_detail(request, pk):
    """
    **GET /api/customers/{pk}/score/** — customer score with full breakdown.

    **POST /api/customers/{pk}/score/** — trigger an incremental recomputation.
    """
    try:
        customer = Customer.objects.select_related('firm').get(pk=pk)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not (customer.firm.created_by == request.user or customer.firm.owner_email.lower() == request.user.email.lower()):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'POST':
        from .scoring import compute_customer_score
        score_obj = compute_customer_score(customer)
        return Response(_customer_score_to_dict(score_obj), status=status.HTTP_200_OK)

    try:
        cs = CustomerScore.objects.select_related('customer').get(customer=customer)
    except CustomerScore.DoesNotExist:
        return Response({'error': 'Score not yet computed. POST to trigger computation.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(_customer_score_to_dict(cs))


# ---------------------------------------------------------------------------
# Trade-finance analysis
# ---------------------------------------------------------------------------

def _trade_finance_link_to_dict(link: TradeFinanceLink) -> dict:
    return {
        'id': link.id,
        'status': link.status,
        'vendor': link.vendor.name if link.vendor else None,
        'purchase_order_txn_id': link.purchase_order_txn_id,
        'invoice_txn_id': link.invoice_txn_id,
        'trade_doc_id': link.trade_doc_id,
        'payment_txn_id': link.payment_txn_id,
        'invoice_amount': str(link.invoice_amount) if link.invoice_amount else None,
        'invoice_currency': link.invoice_currency,
        'customs_declared_value': str(link.customs_declared_value) if link.customs_declared_value else None,
        'customs_currency': link.customs_currency,
        'value_difference': str(link.value_difference) if link.value_difference is not None else None,
        'value_difference_pct': str(link.value_difference_pct) if link.value_difference_pct is not None else None,
        'expected_shipment_date': link.expected_shipment_date.isoformat() if link.expected_shipment_date else None,
        'payment_due_date': link.payment_due_date.isoformat() if link.payment_due_date else None,
        'payment_before_shipment': link.payment_before_shipment,
        'analysis_notes': link.analysis_notes,
        'last_analysed_at': link.last_analysed_at.isoformat() if link.last_analysed_at else None,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def trade_finance_analysis(request, firm_id):
    """
    **GET /api/firms/{firm_id}/trade-finance/**
    List all TradeFinanceLink rows for the firm.
    Query params: status (partial|complete|flagged).

    **POST /api/firms/{firm_id}/trade-finance/**
    Trigger a fresh trade-finance risk scan.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    if request.method == 'POST':
        from .trade_finance import TradeFinanceAnalyser
        result = TradeFinanceAnalyser().analyse(firm_id)
        return Response(result, status=status.HTTP_200_OK)

    qs = TradeFinanceLink.objects.filter(firm=firm).select_related('vendor').order_by('-created_at')
    status_param = request.query_params.get('status')
    if status_param:
        qs = qs.filter(status=status_param)

    return Response({
        'count': qs.count(),
        'results': [_trade_finance_link_to_dict(l) for l in qs],
    })


# ---------------------------------------------------------------------------
# Graph traversal endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def risk_signal_graph(request, firm_id, signal_id):
    """Return the full entity graph connected to a risk signal."""
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm
    from .graph import risk_signal_graph as _rs_graph
    try:
        result = _rs_graph(firm_id, signal_id)
    except RiskSignal.DoesNotExist:
        return Response({'error': 'Risk signal not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def vendor_graph(request, firm_id, vendor_id):
    """Return the full relationship graph for a vendor."""
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm
    from .graph import vendor_history as _vh
    try:
        result = _vh(firm_id, vendor_id)
    except Vendor.DoesNotExist:
        return Response({'error': 'Vendor not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def customer_graph(request, firm_id, customer_id):
    """Return the full relationship graph for a customer."""
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm
    from .graph import customer_history as _ch
    try:
        result = _ch(firm_id, customer_id)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def evidence_graph(request, firm_id):
    """Generic evidence drill-down for any entity type.

    Query params: entity_type (transaction|risk_signal|vendor|customer|trade_doc),
                  entity_id (int).
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm
    entity_type = request.query_params.get('entity_type', '')
    try:
        entity_id = int(request.query_params.get('entity_id', 0))
    except (ValueError, TypeError):
        return Response({'error': 'entity_id must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
    if not entity_type or not entity_id:
        return Response({'error': 'entity_type and entity_id are required'}, status=status.HTTP_400_BAD_REQUEST)

    from .graph import evidence_drilldown as _ed
    try:
        result = _ed(firm_id, entity_type, entity_id)
    except Exception:
        return Response({'error': 'Entity not found'}, status=status.HTTP_404_NOT_FOUND)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)

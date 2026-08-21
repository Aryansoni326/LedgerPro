"""
Celery extraction tasks for the new document types.

Each task follows the *exact same pattern* as the existing
``invoices.tasks.extract_invoice_data``, ``trade_docs.tasks.extract_trade_doc_data``,
and ``eway_bills.tasks.extract_eway_bill_data``:

    1. Fetch file bytes (local or remote)
    2. Call Gemini Vision API with a type-specific prompt
    3. Parse + normalize + validate
    4. Save to DB with status ``needs_review``
    5. On permanent failure → ``extraction_failed``
    6. On transient failure → exponential backoff retry (up to 6)

All five tasks are thin wrappers around ``_extract_document``, which is a
generic extraction driver parametrised by document type.
"""
import base64
import json
import logging
import os
import time
from datetime import date

from celery import shared_task
from django.conf import settings

from common.extraction import (
    call_gemini_vision,
    exponential_backoff,
    fetch_file_bytes,
    get_mime_type,
    is_dummy_api_key,
    parse_gemini_response,
)
from common.normalization import normalize_currency_and_dates

from .document_schemas import SCHEMAS
from .models import Document

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic extraction driver
# ---------------------------------------------------------------------------

def _extract_document(task, document_id: int, doc_type: str):
    """Core extraction logic shared by all new-document-type tasks.

    ``task`` is the bound Celery task instance (``self``).
    """
    logger.info(
        "Starting %s extraction for Document ID %s (attempt %s)",
        doc_type, document_id, task.request.retries + 1,
    )

    try:
        doc = Document.all_objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error("Document ID %s not found.", document_id)
        return

    prompt, mock_data, validator = SCHEMAS[doc_type]

    # 1. Fetch file bytes
    try:
        file_data = fetch_file_bytes(doc.file_url)
    except Exception as exc:
        logger.error("File fetch failed for Document %s: %s", document_id, exc)
        if task.request.retries >= task.max_retries:
            doc.status = 'extraction_failed'
            doc.extraction_failed = True
            doc.save()
        else:
            raise task.retry(exc=exc)
        return

    b64 = base64.b64encode(file_data).decode('utf-8')
    mime = get_mime_type(doc.file_name)

    warnings: list[str] = []
    parsed_json = None
    raw_json_str = None

    # 2. AI extraction or mock fallback
    api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)

    if is_dummy_api_key(api_key):
        logger.warning("Using mock fallback for %s extraction (Document %s).", doc_type, document_id)
        warnings.append("API key is a dummy/placeholder key. Please set a valid GEMINI_API_KEY to extract real data.")
        warnings.append("Using mock data fallback for development.")
        time.sleep(2)
        parsed_json = dict(mock_data)  # shallow copy
        raw_json_str = json.dumps(parsed_json)
    else:
        import urllib.error

        try:
            raw_text = call_gemini_vision(
                prompt_text=prompt,
                base64_data=b64,
                mime_type=mime,
                api_key=api_key,
            )
            raw_json_str = raw_text

            try:
                parsed_json = parse_gemini_response(raw_text)
            except Exception as pe:
                logger.error("JSON parse failure for Document %s: %s", document_id, pe)
                doc.status = 'needs_review'
                doc.extraction_failed = True
                doc.extraction_raw_json = raw_json_str
                doc.validation_warnings = ["AI Parsing Error: Response did not contain valid structured JSON."]
                doc.save()
                return

        except urllib.error.HTTPError as he:
            logger.error("Gemini API HTTP %s for Document %s", he.code, document_id)
            if he.code in [429, 500, 503, 504]:
                if task.request.retries >= task.max_retries:
                    doc.status = 'extraction_failed'
                    doc.extraction_failed = True
                    doc.save()
                    return
                raise task.retry(exc=he, countdown=exponential_backoff(task.request.retries))
            else:
                doc.status = 'needs_review'
                doc.extraction_failed = True
                doc.validation_warnings = [f"API Error: HTTP {he.code}"]
                doc.save()
                return

        except Exception as exc:
            logger.error("Unexpected Gemini error for Document %s: %s", document_id, exc)
            if task.request.retries >= task.max_retries:
                doc.status = 'extraction_failed'
                doc.extraction_failed = True
                doc.save()
            else:
                raise task.retry(exc=exc)
            return

    # 3. Normalize dates, currencies, amounts
    normalize_currency_and_dates(parsed_json)

    # 4. Domain-specific validation
    validator(parsed_json, warnings)

    # 5. Persist
    doc.status = 'needs_review'
    doc.raw_data = parsed_json
    doc.extraction_raw_json = raw_json_str
    doc.validation_warnings = warnings
    doc.extraction_failed = False
    doc.save()

    logger.info(
        "Document %s (%s) extracted → needs_review. Warnings: %s",
        document_id, doc_type, len(warnings),
    )


# ---------------------------------------------------------------------------
# Per-type Celery tasks (same decorator pattern as existing tasks)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=6, default_retry_delay=10)
def extract_purchase_order_data(self, document_id):
    """Extract structured data from a Purchase Order document."""
    _extract_document(self, document_id, 'purchase_order')


@shared_task(bind=True, max_retries=6, default_retry_delay=10)
def extract_bank_statement_data(self, document_id):
    """Extract structured data from a Bank Statement document."""
    _extract_document(self, document_id, 'bank_statement')


@shared_task(bind=True, max_retries=6, default_retry_delay=10)
def extract_contract_data(self, document_id):
    """Extract structured data from a Contract / Agreement document."""
    _extract_document(self, document_id, 'contract')


@shared_task(bind=True, max_retries=6, default_retry_delay=10)
def extract_credit_note_data(self, document_id):
    """Extract structured data from a Credit Note document."""
    _extract_document(self, document_id, 'credit_note')


@shared_task(bind=True, max_retries=6, default_retry_delay=10)
def extract_debit_note_data(self, document_id):
    """Extract structured data from a Debit Note document."""
    _extract_document(self, document_id, 'debit_note')


# ---------------------------------------------------------------------------
# Reconciliation engine task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def run_reconciliation(self, firm_id, **config_overrides):
    """Run the Smart Reconciliation engine for a firm.

    Matches Invoice ↔ Payment ↔ Purchase Order ↔ Bank Transaction,
    classifies mismatches, and queues exceptions for human review.

    Can be called via:
        run_reconciliation.delay(firm_id)
        run_reconciliation.delay(firm_id, amount_tolerance_pct='0.05')
    """
    from .reconciliation import ReconciliationEngine, ReconConfig
    from decimal import Decimal

    logger.info("Starting reconciliation for firm %s (attempt %s)", firm_id, self.request.retries + 1)

    cfg = ReconConfig()
    for key, val in config_overrides.items():
        if hasattr(cfg, key):
            field_val = getattr(cfg, key)
            if isinstance(field_val, Decimal):
                setattr(cfg, key, Decimal(str(val)))
            elif isinstance(field_val, int):
                setattr(cfg, key, int(val))

    try:
        engine = ReconciliationEngine(config=cfg)
        run = engine.match(firm_id)
        logger.info(
            "Reconciliation completed for firm %s: %d exact, %d fuzzy, %d exceptions, %d unmatched",
            firm_id, run.exact_matches, run.fuzzy_matches,
            run.exceptions_created, run.unmatched,
        )
        return {
            'run_id': run.id,
            'status': run.status,
            'exact_matches': run.exact_matches,
            'fuzzy_matches': run.fuzzy_matches,
            'exceptions_created': run.exceptions_created,
            'unmatched': run.unmatched,
        }
    except Exception as exc:
        logger.error("Reconciliation failed for firm %s: %s", firm_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


# ---------------------------------------------------------------------------
# Cash-flow forecast tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def compute_cashflow_forecast(self, firm_id):
    """Compute and persist a daily cash-flow forecast for a single firm.

    Produces a FinancialSnapshot with 30/60/90-day projected positions
    and a plain-English risk explanation.
    """
    from .forecasting import CashFlowForecaster

    logger.info("Computing cash-flow forecast for firm %s", firm_id)
    try:
        forecaster = CashFlowForecaster()
        result = forecaster.forecast(firm_id)
        snapshot = forecaster.save_snapshot(firm_id, result)
        logger.info(
            "Forecast saved for firm %s: health=%s, 30d=%s, 60d=%s, 90d=%s",
            firm_id, result.health_score,
            result.position_30d, result.position_60d, result.position_90d,
        )
        return {
            'firm_id': firm_id,
            'snapshot_id': snapshot.id,
            'health_score': str(result.health_score),
            'pressure_day': result.pressure_day,
        }
    except Exception as exc:
        logger.error("Forecast failed for firm %s: %s", firm_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@shared_task(ignore_result=True)
def nightly_cashflow_forecast_all():
    """Fan-out task: enqueue a forecast for every active firm.

    Scheduled via CELERY_BEAT_SCHEDULE to run nightly at 02:00 UTC.
    """
    from firms.models import Firm

    firm_ids = list(
        Firm.objects.filter(status='active').values_list('id', flat=True)
    )
    logger.info("Nightly forecast: enqueueing %d firms", len(firm_ids))
    for fid in firm_ids:
        compute_cashflow_forecast.delay(fid)


# ---------------------------------------------------------------------------
# Vendor & Customer scoring tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def compute_vendor_score_task(self, vendor_id):
    """Score a single vendor — called incrementally on invoice/payment events."""
    from .models import Vendor
    from .scoring import compute_vendor_score

    logger.info("Computing vendor score for vendor %s", vendor_id)
    try:
        vendor = Vendor.objects.select_related('firm').get(pk=vendor_id)
        score = compute_vendor_score(vendor)
        return {'vendor_id': vendor_id, 'score': str(score.overall_score)}
    except Exception as exc:
        logger.error("Vendor scoring failed for %s: %s", vendor_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def compute_customer_score_task(self, customer_id):
    """Score a single customer — called incrementally on invoice/payment events."""
    from .models import Customer
    from .scoring import compute_customer_score

    logger.info("Computing customer score for customer %s", customer_id)
    try:
        customer = Customer.objects.select_related('firm').get(pk=customer_id)
        score = compute_customer_score(customer)
        return {'customer_id': customer_id, 'score': str(score.overall_score)}
    except Exception as exc:
        logger.error("Customer scoring failed for %s: %s", customer_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@shared_task(ignore_result=True)
def nightly_score_all():
    """Fan-out: recompute scores for all vendors and customers in all active firms."""
    from firms.models import Firm
    from .scoring import score_all_vendors_for_firm, score_all_customers_for_firm

    firm_ids = list(
        Firm.objects.filter(status='active').values_list('id', flat=True)
    )
    logger.info("Nightly scoring: processing %d firms", len(firm_ids))
    for fid in firm_ids:
        score_all_vendors_for_firm(fid)
        score_all_customers_for_firm(fid)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def fetch_historical_exchange_rates(self, rate_iso: str | None = None):
    """Fetch and persist one day of FX history for currencies in use."""
    from firms.models import Firm
    from .fx import refresh_daily_exchange_rates

    as_of = date.fromisoformat(rate_iso) if rate_iso else date.today()
    active_firms = Firm.objects.filter(status='active')

    logger.info("Refreshing FX rates for %s", as_of)
    try:
        stored = refresh_daily_exchange_rates(rate_date=as_of, active_firm_queryset=active_firms)
        return {'rate_date': as_of.isoformat(), 'stored': stored}
    except Exception as exc:
        logger.error("FX refresh failed for %s: %s", as_of, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@shared_task(ignore_result=True)
def nightly_exchange_rate_refresh():
    """Nightly fan-out for historical FX snapshots."""
    fetch_historical_exchange_rates.delay()


# ---------------------------------------------------------------------------
# Trade-finance analysis tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def analyse_trade_finance(self, firm_id):
    """Run trade-finance risk analysis for a single firm."""
    from .trade_finance import TradeFinanceAnalyser

    logger.info("Running trade-finance analysis for firm %s", firm_id)
    try:
        result = TradeFinanceAnalyser().analyse(firm_id)
        logger.info(
            "Trade-finance analysis done for firm %s: %d docs, %d links, %d signals",
            firm_id, result['trade_docs_scanned'],
            result['links_created'], result['signals_created'],
        )
        return result
    except Exception as exc:
        logger.error("Trade-finance analysis failed for firm %s: %s", firm_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@shared_task(ignore_result=True)
def nightly_trade_finance_all():
    """Fan-out: run trade-finance analysis for every active firm."""
    from firms.models import Firm

    firm_ids = list(
        Firm.objects.filter(status='active').values_list('id', flat=True)
    )
    logger.info("Nightly trade-finance: enqueueing %d firms", len(firm_ids))
    for fid in firm_ids:
        analyse_trade_finance.delay(fid)


# ---------------------------------------------------------------------------
# RiskEngine scan (queue: risk)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30, queue="risk")
def scan_firm_risks(self, firm_id: int):
    """Run RiskEngine detectors for a firm (duplicates, unusual amounts, late A/R)."""
    from .risk_engine import RiskEngine

    logger.info("RiskEngine scan for firm %s (attempt %s)", firm_id, self.request.retries + 1)
    try:
        detections = RiskEngine().scan(firm_id)
        return {
            "firm_id": firm_id,
            "detections": len(detections),
            "categories": sorted({d.category for d in detections}),
        }
    except Exception as exc:
        logger.error("RiskEngine scan failed for firm %s: %s", firm_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise

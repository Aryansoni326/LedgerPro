"""
DocumentClassifier — runs before extraction and routes the document to the
correct extraction schema / Celery task.

Two modes:
1. **AI classification** — sends a low-token Gemini Vision request that asks
   only for the document type (no field extraction). Cost: ~50 input tokens.
2. **Rule-based fallback** — inspects filename patterns and first-page text
   (via pypdf) when no valid API key is available.

The classifier returns a ``DocumentType`` string that maps 1:1 to an
extraction task and prompt schema defined in ``intelligence.document_schemas``.
"""
import json
import logging
import os
import re

from common.extraction import (
    call_gemini_vision,
    get_mime_type,
    is_dummy_api_key,
    parse_gemini_response,
)

logger = logging.getLogger(__name__)


# Canonical document types — values match Transaction.TxnType plus the
# three legacy types that already have their own apps.
DOCUMENT_TYPES = frozenset({
    # Legacy (routed to existing apps — classifier can still identify them)
    'invoice',
    'trade_document',
    'eway_bill',
    # New types (routed to intelligence extraction tasks)
    'purchase_order',
    'bank_statement',
    'contract',
    'credit_note',
    'debit_note',
    # Catch-all
    'unknown',
})

# Maps classifier output → existing app task path (for legacy types)
LEGACY_TASK_MAP = {
    'invoice': 'invoices.tasks.extract_invoice_data',
    'trade_document': 'trade_docs.tasks.extract_trade_doc_data',
    'eway_bill': 'eway_bills.tasks.extract_eway_bill_data',
}

# Maps classifier output → intelligence task path (for new types)
INTELLIGENCE_TASK_MAP = {
    'purchase_order': 'intelligence.tasks.extract_purchase_order_data',
    'bank_statement': 'intelligence.tasks.extract_bank_statement_data',
    'contract': 'intelligence.tasks.extract_contract_data',
    'credit_note': 'intelligence.tasks.extract_credit_note_data',
    'debit_note': 'intelligence.tasks.extract_debit_note_data',
}


# ---------------------------------------------------------------------------
# Rule-based fallback patterns
# ---------------------------------------------------------------------------

_FILENAME_PATTERNS: list[tuple[str, str]] = [
    (r'(?i)purchase[_\s-]?order|PO[_\s-]?\d', 'purchase_order'),
    (r'(?i)bank[_\s-]?statement|stmt', 'bank_statement'),
    (r'(?i)contract|agreement|mou', 'contract'),
    (r'(?i)credit[_\s-]?note|CN[_\s-]?\d', 'credit_note'),
    (r'(?i)debit[_\s-]?note|DN[_\s-]?\d', 'debit_note'),
    (r'(?i)e[_\s-]?way|eway', 'eway_bill'),
    (r'(?i)bill[_\s-]?of[_\s-]?entry|shipping[_\s-]?bill|BE[_\s-]?\d', 'trade_document'),
    (r'(?i)invoice|inv[_\s-]?\d|bill(?!.*entry)', 'invoice'),
]

_TEXT_PATTERNS: list[tuple[str, str]] = [
    (r'(?i)purchase\s+order', 'purchase_order'),
    (r'(?i)bank\s+statement|account\s+statement', 'bank_statement'),
    (r'(?i)credit\s+note', 'credit_note'),
    (r'(?i)debit\s+note', 'debit_note'),
    (r'(?i)contract|agreement|terms\s+and\s+conditions', 'contract'),
    (r'(?i)e-?way\s+bill|ewb\s+no', 'eway_bill'),
    (r'(?i)bill\s+of\s+entry|shipping\s+bill|customs', 'trade_document'),
    (r'(?i)tax\s+invoice|invoice\s+no|invoice\s+date', 'invoice'),
]


def _classify_by_filename(filename: str) -> str | None:
    for pattern, doc_type in _FILENAME_PATTERNS:
        if re.search(pattern, filename):
            return doc_type
    return None


def _classify_by_text(text: str) -> str | None:
    for pattern, doc_type in _TEXT_PATTERNS:
        if re.search(pattern, text):
            return doc_type
    return None


def _extract_first_page_text(file_data: bytes) -> str:
    """Best-effort text extraction from the first page of a PDF."""
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_data))
        if reader.pages:
            return reader.pages[0].extract_text() or ''
    except Exception:
        pass
    return ''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_document(
    *,
    file_data: bytes,
    filename: str,
    api_key: str | None = None,
) -> tuple[str, float]:
    """Classify a document and return ``(document_type, confidence)``.

    Tries AI classification first; falls back to filename + text heuristics.
    Confidence is 0.0–1.0 (AI returns its own; heuristics use fixed tiers).
    """
    # Try AI classification
    if api_key and not is_dummy_api_key(api_key):
        try:
            return _classify_with_ai(file_data, filename, api_key)
        except Exception as exc:
            logger.warning("AI classification failed (%s), falling back to rules.", exc)

    # Rule-based fallback
    return _classify_with_rules(file_data, filename)


def _classify_with_ai(
    file_data: bytes,
    filename: str,
    api_key: str,
) -> tuple[str, float]:
    import base64

    prompt = (
        "You are a document classifier for an Indian financial/trade platform.\n"
        "Look at this document and determine its type.\n"
        "Return ONLY a JSON object with exactly these keys:\n"
        '{\n'
        '  "document_type": "one of: invoice, trade_document, eway_bill, '
        'purchase_order, bank_statement, contract, credit_note, debit_note, unknown",\n'
        '  "confidence": number (0.0 to 1.0)\n'
        '}\n'
        "Do not include any explanation or markdown fences."
    )
    mime = get_mime_type(filename)
    b64 = base64.b64encode(file_data).decode('utf-8')

    raw = call_gemini_vision(
        prompt_text=prompt,
        base64_data=b64,
        mime_type=mime,
        api_key=api_key,
    )
    result = parse_gemini_response(raw)
    doc_type = str(result.get('document_type', 'unknown')).strip().lower()
    confidence = float(result.get('confidence', 0.0))

    if doc_type not in DOCUMENT_TYPES:
        doc_type = 'unknown'

    return doc_type, confidence


def _classify_with_rules(
    file_data: bytes,
    filename: str,
) -> tuple[str, float]:
    # Filename heuristic (high confidence)
    result = _classify_by_filename(filename)
    if result:
        return result, 0.75

    # First-page text heuristic (medium confidence)
    text = _extract_first_page_text(file_data)
    if text:
        result = _classify_by_text(text)
        if result:
            return result, 0.60

    return 'unknown', 0.0

"""
Currency and date normalization for all extraction pipelines.

Every extractor calls ``normalize_currency_and_dates`` on its parsed JSON
*before* running domain-specific validation rules. This guarantees a
consistent shape regardless of which model/parser produced the data.
"""
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import dateutil.parser

logger = logging.getLogger(__name__)

# ISO 4217 codes we expect in Indian trade/finance documents
_KNOWN_CURRENCIES = frozenset({
    'INR', 'USD', 'EUR', 'GBP', 'AED', 'SGD', 'JPY', 'CNY', 'AUD', 'CAD',
    'CHF', 'HKD', 'SAR', 'QAR', 'KWD', 'BHD', 'OMR', 'MYR', 'THB', 'ZAR',
})

# Common currency symbols to ISO code
_SYMBOL_MAP = {
    '₹': 'INR', '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY',
    'Rs': 'INR', 'Rs.': 'INR',
}

# Fields that should be parsed as dates (ISO YYYY-MM-DD)
_DATE_FIELDS = frozenset({
    'invoice_date', 'be_date', 'po_date', 'statement_date',
    'contract_date', 'due_date', 'start_date', 'end_date',
    'note_date', 'period_start', 'period_end',
})

# Fields that should be coerced to Decimal / float
_AMOUNT_FIELDS = frozenset({
    'taxable_amount', 'assessable_amount', 'total_amount',
    'cgst', 'sgst', 'igst', 'cess',
    'assessable_value', 'gross_weight', 'net_weight',
    'amount', 'net_amount', 'tax_amount', 'total',
    'opening_balance', 'closing_balance',
    'total_credits', 'total_debits',
    'original_amount', 'adjusted_amount',
})


def normalize_date(value: str | None) -> str | None:
    """Coerce a date string into ISO YYYY-MM-DD or return None."""
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    # Already ISO
    if re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
        return raw

    # Common Indian formats
    for fmt in ('%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d-%m-%Y',
                '%d.%m.%Y', '%m/%d/%Y', '%Y/%m/%d', '%d %b %Y',
                '%d %B %Y', '%b %d, %Y', '%B %d, %Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue

    # Fallback to dateutil
    try:
        return dateutil.parser.parse(raw, dayfirst=True).strftime('%Y-%m-%d')
    except Exception:
        logger.warning("Could not parse date value: %r", raw)
        return raw  # preserve original so validation can flag it


def normalize_amount(value) -> float:
    """Coerce an amount to a clean float; strips currency symbols and commas."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    # Strip known currency symbols
    for sym in _SYMBOL_MAP:
        raw = raw.replace(sym, '')
    raw = raw.replace(',', '').replace(' ', '').strip()
    if not raw:
        return 0.0
    try:
        return float(Decimal(raw))
    except (InvalidOperation, ValueError):
        logger.warning("Could not parse amount value: %r", value)
        return 0.0


def normalize_currency(value: str | None) -> str:
    """Normalize a currency string to a 3-letter ISO code. Defaults to INR."""
    if not value:
        return 'INR'
    raw = str(value).strip()

    # Direct symbol match
    mapped = _SYMBOL_MAP.get(raw)
    if mapped:
        return mapped

    upper = raw.upper()
    if upper in _KNOWN_CURRENCIES:
        return upper

    # Partial match (e.g. "US Dollars" -> USD)
    if 'RUPEE' in upper or 'INR' in upper:
        return 'INR'
    if 'DOLLAR' in upper and 'US' in upper:
        return 'USD'
    if 'EURO' in upper:
        return 'EUR'
    if 'POUND' in upper:
        return 'GBP'

    logger.warning("Unknown currency %r, defaulting to INR", value)
    return 'INR'


def normalize_currency_and_dates(data: dict) -> dict:
    """In-place normalize all date fields, amount fields, and currency in
    an extracted JSON dict. Returns the same dict for chaining.

    This is the single entry-point every extractor calls after parsing the
    AI / fallback response and before running validation rules.
    """
    # Dates
    for key in list(data.keys()):
        if key in _DATE_FIELDS:
            data[key] = normalize_date(data[key])

    # Amounts
    for key in list(data.keys()):
        if key in _AMOUNT_FIELDS:
            data[key] = normalize_amount(data[key])

    # Currency
    if 'currency' in data:
        data['currency'] = normalize_currency(data['currency'])

    return data

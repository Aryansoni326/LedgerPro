"""
Historical FX services for multi-currency transactions and settlements.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .models import ExchangeRate

logger = logging.getLogger(__name__)

RATE_Q = Decimal("0.00000001")
AMOUNT_Q = Decimal("0.01")


def _upper(code: str | None, default: str = "INR") -> str:
    return (code or default).strip().upper() or default


def _to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(RATE_Q, rounding=ROUND_HALF_UP)


def quantize_amount(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(AMOUNT_Q, rounding=ROUND_HALF_UP)


def get_historical_rate(
    from_currency: str,
    to_currency: str,
    rate_date: date,
    *,
    allow_fetch: bool = True,
) -> Decimal:
    """Resolve an FX rate for a given date, falling back to the most recent
    stored prior date if the market was closed on the requested day.
    """
    from_currency = _upper(from_currency)
    to_currency = _upper(to_currency)
    if from_currency == to_currency:
        return Decimal("1.00000000")

    existing = (
        ExchangeRate.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date__lte=rate_date,
        )
        .order_by("-rate_date")
        .first()
    )
    if existing:
        return existing.rate

    if allow_fetch:
        fetch_and_store_rates(rate_date, from_currency, [to_currency])
        existing = (
            ExchangeRate.objects.filter(
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date__lte=rate_date,
            )
            .order_by("-rate_date")
            .first()
        )
        if existing:
            return existing.rate

    raise ValueError(
        f"No FX rate available for {from_currency}->{to_currency} on or before {rate_date}."
    )


def annotate_transaction_fx(transaction) -> None:
    """Populate transaction-time FX fields in memory."""
    base_currency = _upper(getattr(transaction.firm, "base_currency", None))
    txn_currency = _upper(getattr(transaction, "currency", None), default=base_currency)

    transaction.currency = txn_currency
    transaction.base_currency = base_currency

    rate = get_historical_rate(txn_currency, base_currency, transaction.txn_date)
    transaction.exchange_rate = rate
    transaction.base_currency_amount = quantize_amount(Decimal(str(transaction.amount)) * rate)


def snapshot_settlement_fx(link, txn_a, txn_b) -> None:
    """Lock realised FX on a reconciliation link at settlement time.

    Treat the first invoice leg we can find as the original exposure and the
    other leg as the settlement leg.
    """
    original = txn_a if txn_a.txn_type == "invoice" else txn_b
    settlement = txn_b if original is txn_a else txn_a

    if original.exchange_rate is None or original.base_currency_amount is None:
        annotate_transaction_fx(original)
    if settlement.exchange_rate is None or settlement.base_currency_amount is None:
        annotate_transaction_fx(settlement)

    link.settlement_currency = settlement.currency
    link.settlement_exchange_rate = settlement.exchange_rate
    link.original_base_amount = original.base_currency_amount
    link.settlement_base_amount = settlement.base_currency_amount
    link.fx_difference = quantize_amount(
        Decimal(str(settlement.base_currency_amount)) - Decimal(str(original.base_currency_amount))
    )


def fetch_and_store_rates(
    rate_date: date,
    base_currency: str,
    quote_currencies: Iterable[str],
    *,
    source: str = "open_er_api",
) -> int:
    """Fetch a historical daily snapshot and upsert all requested pairs."""
    base_currency = _upper(base_currency)
    quotes = sorted({_upper(c) for c in quote_currencies if _upper(c) != base_currency})
    if not quotes:
        return 0

    url = f"https://api.frankfurter.app/{rate_date.isoformat()}?from={base_currency}&to={','.join(quotes)}"
    logger.info("Fetching FX rates for %s -> %s on %s", base_currency, ",".join(quotes), rate_date)

    with urllib.request.urlopen(url, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    rates = payload.get("rates") or {}
    count = 0
    for quote in quotes:
        raw_rate = rates.get(quote)
        if raw_rate is None:
            continue
        ExchangeRate.objects.update_or_create(
            from_currency=base_currency,
            to_currency=quote,
            rate_date=rate_date,
            defaults={
                "rate": _to_decimal(raw_rate),
                "source": source,
                "metadata": {"api_date": payload.get("date"), "provider": source, "url": url},
            },
        )
        count += 1
    return count


def refresh_daily_exchange_rates(*, rate_date: date, active_firm_queryset) -> int:
    """Collect the currency graph from current data and persist one daily snapshot."""
    from .models import Transaction

    base_currencies = {
        _upper(code)
        for code in active_firm_queryset.values_list("base_currency", flat=True)
    }
    txn_currencies = {
        _upper(code)
        for code in Transaction.objects.filter(is_deleted=False).values_list("currency", flat=True)
        if code
    }
    settlement_currencies = {
        _upper(code)
        for code in Transaction.objects.filter(is_deleted=False).values_list("base_currency", flat=True)
        if code
    }
    all_currencies = (base_currencies | txn_currencies | settlement_currencies) - {""}

    stored = 0
    for base_currency in sorted(base_currencies or {"INR"}):
        targets = sorted(c for c in all_currencies if c != base_currency)
        stored += fetch_and_store_rates(rate_date, base_currency, targets)
    return stored

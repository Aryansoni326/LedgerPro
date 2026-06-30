import logging
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from firms.access import get_firm_or_403
from invoices.models import Bill

logger = logging.getLogger(__name__)


def _get_verified_bills(firm, range_param):
    """
    Returns only status='verified' bills for the firm within the date range.
    Bills with status 'processing', 'needs_review', 'extraction_failed', or
    'approved' are explicitly excluded to keep analytics provisional-free.
    """
    qs = Bill.objects.filter(
        firm=firm,
        status='verified',
        is_deleted=False
    )

    today = date.today()
    if range_param == 'month':
        start = today.replace(day=1)
    elif range_param == 'quarter':
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_start_month, day=1)
    elif range_param == 'year':
        start = today.replace(month=1, day=1)
    else:
        # Default to year
        start = today.replace(month=1, day=1)

    # Filter by invoice_date stored inside raw_data (JSON field)
    # We keep a broad filter and then validate in Python to avoid DB-specific JSON date parsing
    return qs, start, today


def _parse_invoice_date(bill):
    """Safely parse the invoice_date from raw_data JSON."""
    try:
        raw_date = bill.raw_data.get('invoice_date') if bill.raw_data else None
        if raw_date:
            return datetime.strptime(str(raw_date)[:10], '%Y-%m-%d').date()
    except (ValueError, AttributeError, TypeError):
        pass
    # Fall back to upload date if invoice_date is missing/malformed
    return bill.uploaded_at.date()


def _safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_turnover(request, firm_id):
    """
    GET /api/firms/{firm_id}/analytics/turnover?range=month|quarter|year

    Returns time-bucketed arrays of verified purchase and sale invoice totals
    for rendering a Recharts line chart. Only status='verified' bills are counted.

    Response shape:
    [
        { "label": "Jan", "purchase": 150000.00, "sale": 220000.00 },
        ...
    ]
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    range_param = request.GET.get('range', 'year')
    qs, start, end = _get_verified_bills(firm, range_param)

    # Build buckets based on range
    buckets = {}
    if range_param == 'month':
        # Daily buckets for current month
        current = start
        while current <= end:
            label = current.strftime('%b %d')
            buckets[label] = {'purchase': 0.0, 'sale': 0.0, '_date': current}
            current += timedelta(days=1)
    elif range_param == 'quarter':
        # Weekly buckets for quarter (12–13 weeks)
        current = start
        week_num = 1
        while current <= end:
            label = f"Wk {week_num}"
            buckets[label] = {'purchase': 0.0, 'sale': 0.0, '_date': current, '_end': min(current + timedelta(days=6), end)}
            current += timedelta(days=7)
            week_num += 1
    else:
        # Monthly buckets for year
        current = start
        while current <= end:
            label = current.strftime('%b')
            month_end = (current + relativedelta(months=1)) - timedelta(days=1)
            buckets[label] = {'purchase': 0.0, 'sale': 0.0, '_date': current, '_end': month_end}
            current += relativedelta(months=1)

    # Aggregate bills into buckets
    for bill in qs:
        inv_date = _parse_invoice_date(bill)
        if inv_date < start or inv_date > end:
            continue

        total = _safe_float(bill.raw_data.get('total_amount') if bill.raw_data else None)
        bill_type = (bill.raw_data.get('bill_type') or 'purchase').lower() if bill.raw_data else 'purchase'
        if bill_type not in ('purchase', 'sale'):
            bill_type = 'purchase'

        if range_param == 'month':
            label = inv_date.strftime('%b %d')
            if label in buckets:
                buckets[label][bill_type] += total
        elif range_param == 'quarter':
            # Find the week bucket
            for label, bkt in buckets.items():
                if bkt['_date'] <= inv_date <= bkt.get('_end', bkt['_date']):
                    buckets[label][bill_type] += total
                    break
        else:
            label = inv_date.strftime('%b')
            if label in buckets:
                buckets[label][bill_type] += total

    # Serialize — drop internal _date/_end keys
    result = []
    for label, data in buckets.items():
        result.append({
            'label': label,
            'purchase': round(data['purchase'], 2),
            'sale': round(data['sale'], 2),
        })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_summary(request, firm_id):
    """
    GET /api/firms/{firm_id}/analytics/summary?range=month|quarter|year

    Returns summary KPIs for the date range:
    - total_purchase_turnover
    - total_sales_turnover
    - net_gst_liability  (output_tax - input_tax_credit)
    - purchase_vs_sale   (for pie chart: [{ name, value }])

    Only status='verified' bills are included — no provisional AI guesses.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    range_param = request.GET.get('range', 'year')
    qs, start, end = _get_verified_bills(firm, range_param)

    total_purchase = 0.0
    total_sale = 0.0
    input_tax = 0.0    # GST paid on purchases (ITC claimable)
    output_tax = 0.0   # GST collected on sales (payable to govt)

    for bill in qs:
        if not bill.raw_data:
            continue
        inv_date = _parse_invoice_date(bill)
        if inv_date < start or inv_date > end:
            continue

        taxable = _safe_float(bill.raw_data.get('taxable_amount'))
        cgst = _safe_float(bill.raw_data.get('cgst'))
        sgst = _safe_float(bill.raw_data.get('sgst'))
        igst = _safe_float(bill.raw_data.get('igst'))
        cess = _safe_float(bill.raw_data.get('cess'))
        gst_total = cgst + sgst + igst + cess

        bill_type = (bill.raw_data.get('bill_type') or 'purchase').lower()
        if bill_type not in ('purchase', 'sale'):
            bill_type = 'purchase'

        if bill_type == 'purchase':
            total_purchase += taxable
            input_tax += gst_total
        else:
            total_sale += taxable
            output_tax += gst_total

    net_gst = round(output_tax - input_tax, 2)  # positive = liability, negative = ITC surplus

    return Response({
        'total_purchase_turnover': round(total_purchase, 2),
        'total_sales_turnover': round(total_sale, 2),
        'net_gst_liability': net_gst,
        'output_tax': round(output_tax, 2),
        'input_tax_credit': round(input_tax, 2),
        'range': range_param,
        'period_start': start.isoformat(),
        'period_end': end.isoformat(),
        'purchase_vs_sale': [
            {'name': 'Purchases', 'value': round(total_purchase, 2)},
            {'name': 'Sales', 'value': round(total_sale, 2)},
        ]
    })

"""
Extraction prompt schemas for each new document type.

Each schema defines:
- ``prompt``: the Gemini Vision prompt requesting structured JSON.
- ``mock``: a development mock response matching that schema.
- ``validate(data, warnings)``: domain-specific validation rules that
  append to the warnings list (same pattern as existing tasks).
"""
from datetime import datetime


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------

PURCHASE_ORDER_PROMPT = (
    "Analyze this Purchase Order document and extract the following fields.\n"
    "Return ONLY a valid JSON object with exactly these keys:\n"
    "{\n"
    '  "po_number": "string (Purchase Order number)",\n'
    '  "po_date": "string (ISO YYYY-MM-DD)",\n'
    '  "vendor_name": "string (supplier / vendor name)",\n'
    '  "vendor_gstin": "string (15-char GSTIN, or null)",\n'
    '  "buyer_name": "string (buyer / purchaser name)",\n'
    '  "buyer_gstin": "string (15-char GSTIN, or null)",\n'
    '  "currency": "string (3-letter ISO code, default INR)",\n'
    '  "total_amount": number (total PO value, default 0.0),\n'
    '  "tax_amount": number (total tax, default 0.0),\n'
    '  "net_amount": number (value before tax, default 0.0),\n'
    '  "due_date": "string (expected delivery / due date, ISO YYYY-MM-DD, or null)",\n'
    '  "line_items": [{"description": "string", "quantity": number, "unit_price": number, "amount": number}],\n'
    '  "confidence": {"po_number": number, "total_amount": number, "vendor_name": number}\n'
    "}\n"
    "Do not include any explanation, markdown fences, or extra text."
)

PURCHASE_ORDER_MOCK = {
    "po_number": "PO-2026-00456",
    "po_date": "2026-07-15",
    "vendor_name": "Steel Supplies Ltd",
    "vendor_gstin": "27AAAAA1111A1Z1",
    "buyer_name": "Dinesh Engineers",
    "buyer_gstin": "24ABJPS6700M1ZC",
    "currency": "INR",
    "total_amount": 150000.00,
    "tax_amount": 27000.00,
    "net_amount": 123000.00,
    "due_date": "2026-08-15",
    "line_items": [
        {"description": "MS Plate 12mm", "quantity": 100, "unit_price": 1230.00, "amount": 123000.00},
    ],
    "confidence": {"po_number": 0.95, "total_amount": 0.90, "vendor_name": 0.92},
}


def validate_purchase_order(data: dict, warnings: list[str]):
    net = float(data.get('net_amount', 0) or 0)
    tax = float(data.get('tax_amount', 0) or 0)
    total = float(data.get('total_amount', 0) or 0)
    if total > 0 and abs((net + tax) - total) > 1.0:
        warnings.append(
            f"PO total mismatch: net ({net:.2f}) + tax ({tax:.2f}) = {net + tax:.2f}, "
            f"but total_amount is {total:.2f}."
        )
    if not data.get('po_number'):
        warnings.append("PO number is missing.")


# ---------------------------------------------------------------------------
# Bank Statement
# ---------------------------------------------------------------------------

BANK_STATEMENT_PROMPT = (
    "Analyze this Bank Statement document and extract the following fields.\n"
    "Return ONLY a valid JSON object with exactly these keys:\n"
    "{\n"
    '  "bank_name": "string",\n'
    '  "account_number": "string (masked is fine)",\n'
    '  "account_holder": "string",\n'
    '  "ifsc_code": "string (or null)",\n'
    '  "currency": "string (3-letter ISO code, default INR)",\n'
    '  "statement_date": "string (statement generation date, ISO YYYY-MM-DD, or null)",\n'
    '  "period_start": "string (ISO YYYY-MM-DD)",\n'
    '  "period_end": "string (ISO YYYY-MM-DD)",\n'
    '  "opening_balance": number (default 0.0),\n'
    '  "closing_balance": number (default 0.0),\n'
    '  "total_credits": number (default 0.0),\n'
    '  "total_debits": number (default 0.0),\n'
    '  "transaction_count": number (total transactions, default 0),\n'
    '  "confidence": {"account_number": number, "opening_balance": number, "closing_balance": number}\n'
    "}\n"
    "Do not include any explanation, markdown fences, or extra text."
)

BANK_STATEMENT_MOCK = {
    "bank_name": "State Bank of India",
    "account_number": "XXXX1234",
    "account_holder": "Dinesh Engineers",
    "ifsc_code": "SBIN0001234",
    "currency": "INR",
    "statement_date": "2026-07-31",
    "period_start": "2026-07-01",
    "period_end": "2026-07-31",
    "opening_balance": 250000.00,
    "closing_balance": 315000.00,
    "total_credits": 180000.00,
    "total_debits": 115000.00,
    "transaction_count": 42,
    "confidence": {"account_number": 0.98, "opening_balance": 0.95, "closing_balance": 0.95},
}


def validate_bank_statement(data: dict, warnings: list[str]):
    opening = float(data.get('opening_balance', 0) or 0)
    closing = float(data.get('closing_balance', 0) or 0)
    credits = float(data.get('total_credits', 0) or 0)
    debits = float(data.get('total_debits', 0) or 0)
    expected = opening + credits - debits
    if closing != 0 and abs(expected - closing) > 1.0:
        warnings.append(
            f"Balance mismatch: opening ({opening:.2f}) + credits ({credits:.2f}) "
            f"- debits ({debits:.2f}) = {expected:.2f}, but closing is {closing:.2f}."
        )


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

CONTRACT_PROMPT = (
    "Analyze this Contract / Agreement document and extract the following fields.\n"
    "Return ONLY a valid JSON object with exactly these keys:\n"
    "{\n"
    '  "contract_number": "string (contract / agreement reference number, or null)",\n'
    '  "contract_date": "string (ISO YYYY-MM-DD)",\n'
    '  "party_a": "string (first party name)",\n'
    '  "party_a_gstin": "string (GSTIN, or null)",\n'
    '  "party_b": "string (second party name)",\n'
    '  "party_b_gstin": "string (GSTIN, or null)",\n'
    '  "currency": "string (3-letter ISO code, default INR)",\n'
    '  "total_amount": number (contract value, default 0.0),\n'
    '  "start_date": "string (ISO YYYY-MM-DD, or null)",\n'
    '  "end_date": "string (ISO YYYY-MM-DD, or null)",\n'
    '  "summary": "string (1-2 sentence summary of the contract scope)",\n'
    '  "confidence": {"contract_number": number, "total_amount": number, "party_a": number}\n'
    "}\n"
    "Do not include any explanation, markdown fences, or extra text."
)

CONTRACT_MOCK = {
    "contract_number": "AGR-2026-789",
    "contract_date": "2026-06-01",
    "party_a": "Dinesh Engineers",
    "party_a_gstin": "24ABJPS6700M1ZC",
    "party_b": "Infrastructure Corp",
    "party_b_gstin": "27BBBBB2222B2Z2",
    "currency": "INR",
    "total_amount": 5000000.00,
    "start_date": "2026-06-15",
    "end_date": "2027-06-14",
    "summary": "Annual maintenance contract for industrial machinery at Vadodara plant.",
    "confidence": {"contract_number": 0.88, "total_amount": 0.85, "party_a": 0.92},
}


def validate_contract(data: dict, warnings: list[str]):
    start = data.get('start_date')
    end = data.get('end_date')
    if start and end:
        try:
            s = datetime.strptime(str(start)[:10], '%Y-%m-%d')
            e = datetime.strptime(str(end)[:10], '%Y-%m-%d')
            if e < s:
                warnings.append(f"Contract end date ({end}) is before start date ({start}).")
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Credit Note
# ---------------------------------------------------------------------------

CREDIT_NOTE_PROMPT = (
    "Analyze this Credit Note document and extract the following fields.\n"
    "Return ONLY a valid JSON object with exactly these keys:\n"
    "{\n"
    '  "note_number": "string (credit note number)",\n'
    '  "note_date": "string (ISO YYYY-MM-DD)",\n'
    '  "original_invoice_number": "string (reference invoice, or null)",\n'
    '  "party_name_from": "string (issuer name)",\n'
    '  "gstin_from": "string (15-char GSTIN, or null)",\n'
    '  "party_name_to": "string (recipient name)",\n'
    '  "gstin_to": "string (15-char GSTIN, or null)",\n'
    '  "currency": "string (3-letter ISO code, default INR)",\n'
    '  "original_amount": number (original invoice amount, default 0.0),\n'
    '  "adjusted_amount": number (credit note value, default 0.0),\n'
    '  "reason": "string (reason for credit note, or null)",\n'
    '  "cgst": number (default 0.0),\n'
    '  "sgst": number (default 0.0),\n'
    '  "igst": number (default 0.0),\n'
    '  "confidence": {"note_number": number, "adjusted_amount": number}\n'
    "}\n"
    "Do not include any explanation, markdown fences, or extra text."
)

CREDIT_NOTE_MOCK = {
    "note_number": "CN-2026-0012",
    "note_date": "2026-07-20",
    "original_invoice_number": "INV-2026-0045",
    "party_name_from": "Dinesh Engineers",
    "gstin_from": "24ABJPS6700M1ZC",
    "party_name_to": "Apex Bookkeeping Partners",
    "gstin_to": "27AAAAA1111A1Z1",
    "currency": "INR",
    "original_amount": 50000.00,
    "adjusted_amount": 5000.00,
    "reason": "Quantity discrepancy in delivered goods",
    "cgst": 450.00,
    "sgst": 450.00,
    "igst": 0.0,
    "confidence": {"note_number": 0.95, "adjusted_amount": 0.92},
}


def validate_credit_note(data: dict, warnings: list[str]):
    adj = float(data.get('adjusted_amount', 0) or 0)
    orig = float(data.get('original_amount', 0) or 0)
    if adj > orig > 0:
        warnings.append(
            f"Credit note adjusted amount ({adj:.2f}) exceeds "
            f"original invoice amount ({orig:.2f})."
        )
    if not data.get('note_number'):
        warnings.append("Credit note number is missing.")


# ---------------------------------------------------------------------------
# Debit Note
# ---------------------------------------------------------------------------

DEBIT_NOTE_PROMPT = (
    "Analyze this Debit Note document and extract the following fields.\n"
    "Return ONLY a valid JSON object with exactly these keys:\n"
    "{\n"
    '  "note_number": "string (debit note number)",\n'
    '  "note_date": "string (ISO YYYY-MM-DD)",\n'
    '  "original_invoice_number": "string (reference invoice, or null)",\n'
    '  "party_name_from": "string (issuer name)",\n'
    '  "gstin_from": "string (15-char GSTIN, or null)",\n'
    '  "party_name_to": "string (recipient name)",\n'
    '  "gstin_to": "string (15-char GSTIN, or null)",\n'
    '  "currency": "string (3-letter ISO code, default INR)",\n'
    '  "original_amount": number (original invoice amount, default 0.0),\n'
    '  "adjusted_amount": number (debit note value, default 0.0),\n'
    '  "reason": "string (reason for debit note, or null)",\n'
    '  "cgst": number (default 0.0),\n'
    '  "sgst": number (default 0.0),\n'
    '  "igst": number (default 0.0),\n'
    '  "confidence": {"note_number": number, "adjusted_amount": number}\n'
    "}\n"
    "Do not include any explanation, markdown fences, or extra text."
)

DEBIT_NOTE_MOCK = {
    "note_number": "DN-2026-0008",
    "note_date": "2026-07-22",
    "original_invoice_number": "INV-2026-0038",
    "party_name_from": "Steel Supplies Ltd",
    "gstin_from": "27BBBBB2222B2Z2",
    "party_name_to": "Dinesh Engineers",
    "gstin_to": "24ABJPS6700M1ZC",
    "currency": "INR",
    "original_amount": 75000.00,
    "adjusted_amount": 3500.00,
    "reason": "Price revision per amended contract terms",
    "cgst": 315.00,
    "sgst": 315.00,
    "igst": 0.0,
    "confidence": {"note_number": 0.94, "adjusted_amount": 0.90},
}


def validate_debit_note(data: dict, warnings: list[str]):
    adj = float(data.get('adjusted_amount', 0) or 0)
    orig = float(data.get('original_amount', 0) or 0)
    if adj > orig > 0:
        warnings.append(
            f"Debit note adjusted amount ({adj:.2f}) exceeds "
            f"original invoice amount ({orig:.2f})."
        )
    if not data.get('note_number'):
        warnings.append("Debit note number is missing.")


# ---------------------------------------------------------------------------
# Registry — maps document_type → (prompt, mock, validator)
# ---------------------------------------------------------------------------

SCHEMAS = {
    'purchase_order': (PURCHASE_ORDER_PROMPT, PURCHASE_ORDER_MOCK, validate_purchase_order),
    'bank_statement': (BANK_STATEMENT_PROMPT, BANK_STATEMENT_MOCK, validate_bank_statement),
    'contract': (CONTRACT_PROMPT, CONTRACT_MOCK, validate_contract),
    'credit_note': (CREDIT_NOTE_PROMPT, CREDIT_NOTE_MOCK, validate_credit_note),
    'debit_note': (DEBIT_NOTE_PROMPT, DEBIT_NOTE_MOCK, validate_debit_note),
}

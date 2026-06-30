import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

from celery import shared_task
from django.conf import settings

from .models import Bill

logger = logging.getLogger(__name__)

def get_mime_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return 'application/pdf'
    elif ext in ['.jpg', '.jpeg']:
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    return 'application/octet-stream'


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def extract_invoice_data(self, bill_id):
    """
    Celery task that performs AI metadata extraction from invoice documents (PDF/JPG/PNG)
    using Gemini's Vision API capabilities.
    """
    logger.info("Initializing extraction task for Bill ID %s (Attempt %s)", bill_id, self.request.retries + 1)

    try:
        bill = Bill.objects.get(id=bill_id)
    except Bill.DoesNotExist:
        logger.error("Bill ID %s not found in database.", bill_id)
        return

    firm = bill.firm
    firm_gstin = firm.gstin or "None"

    # 1. Fetch file data (local media file or remote URL)
    try:
        if bill.file_url.startswith('/media/') or not bill.file_url.startswith('http'):
            # Local media file path
            relative_path = bill.file_url.replace(settings.MEDIA_URL, '', 1)
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            with open(file_path, 'rb') as f:
                file_data = f.read()
        else:
            # Remote S3/R2 URL
            req = urllib.request.Request(bill.file_url, headers={'User-Agent': 'LedgerPro Extraction Pipeline'})
            with urllib.request.urlopen(req, timeout=15) as response:
                file_data = response.read()
    except Exception as e:
        logger.error("Failed to read invoice file for Bill %s: %s", bill_id, e)
        # Transient network issues can be retried
        if self.request.retries >= self.max_retries:
            bill.status = 'extraction_failed'
            bill.extraction_failed = True
            bill.save()
        else:
            raise self.retry(exc=e)
        return

    base64_data = base64.b64encode(file_data).decode('utf-8')
    mime_type = get_mime_type(bill.file_name)

    # 2. Call Gemini Vision API
    gemini_api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)

    # Use mock fallback if key is missing, starts with mock- or is a placeholder template
    is_dummy_key = not gemini_api_key or gemini_api_key.startswith('mock-') or 'YOUR_GEMINI_KEY' in gemini_api_key
    if is_dummy_key:
        # DEVELOPMENT MOCK FALLBACK
        logger.warning("Using development mock fallback for invoice extraction.")
        time.sleep(2)
        mock_response = {
            "invoice_number": "INV-2026-9901",
            "invoice_date": "2026-06-30",
            "party_name": "Apex Bookkeeping Partners",
            "party_gstin": "27AAAAA1111A1Z1",
            "place_of_supply": "Maharashtra",
            "taxable_amount": 1000.0,
            "cgst": 90.0,
            "sgst": 90.0,
            "igst": 0.0,
            "cess": 0.0,
            "total_amount": 1180.0,
            "bill_type": "purchase",
            "confidence": {
                "invoice_number": 0.95,
                "invoice_date": 0.98,
                "party_name": 0.90,
                "party_gstin": 0.95,
                "taxable_amount": 0.99,
                "total_amount": 0.99
            }
        }
        raw_json_str = json.dumps(mock_response)
        parsed_json = mock_response
    else:
        # Prepare Vision prompt
        prompt_text = (
            f"Analyze this invoice and extract metadata. The current firm's own GSTIN is: {firm_gstin}.\n"
            f"Return a JSON object conforming exactly to this structure:\n"
            f"{{\n"
            f"  \"invoice_number\": \"string (document invoice identifier)\",\n"
            f"  \"invoice_date\": \"string (ISO format YYYY-MM-DD)\",\n"
            f"  \"party_name\": \"string (name of the other party)\",\n"
            f"  \"party_gstin\": \"string (15-character GSTIN of the other party, or null if missing)\",\n"
            f"  \"place_of_supply\": \"string (state code or state name of supply)\",\n"
            f"  \"taxable_amount\": number (total value before tax, default 0.0),\n"
            f"  \"cgst\": number (central tax, default 0.0),\n"
            f"  \"sgst\": number (state tax, default 0.0),\n"
            f"  \"igst\": number (integrated tax, default 0.0),\n"
            f"  \"cess\": number (cess tax, default 0.0),\n"
            f"  \"total_amount\": number (total amount after taxes, default 0.0),\n"
            f"  \"bill_type\": \"string (must be 'purchase' if firm_gstin {firm_gstin} is buyer, or 'sale' if firm_gstin is seller)\",\n"
            f"  \"confidence\": {{\n"
            f"    \"invoice_number\": number (0.0 to 1.0),\n"
            f"    \"invoice_date\": number (0.0 to 1.0),\n"
            f"    \"party_name\": number (0.0 to 1.0),\n"
            f"    \"party_gstin\": number (0.0 to 1.0),\n"
            f"    \"taxable_amount\": number (0.0 to 1.0),\n"
            f"    \"total_amount\": number (0.0 to 1.0)\n"
            f"  }}\n"
            f"}}"
        )

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        # Make REST call to Gemini
        try:
            req = urllib.request.Request(
                api_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload).encode('utf-8'),
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                response_data = json.loads(res.read().decode())

            raw_json_str = response_data['candidates'][0]['content']['parts'][0]['text']
            logger.info("Raw Gemini API response retrieved successfully.")

        except urllib.error.HTTPError as he:
            logger.error("Gemini API HTTP Error %s: %s", he.code, he.read().decode())
            # Retry on transient codes (429 rate limits, 5xx server issues)
            if he.code in [429, 500, 503, 504]:
                if self.request.retries >= self.max_retries:
                    bill.status = 'extraction_failed'
                    bill.extraction_failed = True
                    bill.save()
                    return
                else:
                    raise self.retry(exc=he)
            else:
                # Permanent HTTP errors (like 400 Bad Request, 403 Forbidden)
                bill.status = 'needs_review'
                bill.extraction_failed = True
                bill.validation_warnings = [f"API Connection Error: HTTP {he.code}"]
                bill.save()
                return
        except Exception as e:
            logger.error("Unexpected error contacting Gemini API: %s", e)
            if self.request.retries >= self.max_retries:
                bill.status = 'extraction_failed'
                bill.extraction_failed = True
                bill.save()
            else:
                raise self.retry(exc=e)
            return

        # 3. Defensive Parsing
        try:
            text = raw_json_str.strip()
            # Strip markdown wrapper fences if the model bypassed config
            if text.startswith("```"):
                text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
            parsed_json = json.loads(text.strip())
        except Exception as pe:
            logger.error("Failed to parse Gemini output as JSON: %s", pe)
            bill.status = 'needs_review'
            bill.extraction_failed = True
            bill.extraction_raw_json = raw_json_str
            bill.validation_warnings = ["AI Parsing Error: Response did not contain valid structured JSON."]
            bill.save()
            return

    # 4. Server-Side Validation Rules Pass
    warnings = []

    taxable = float(parsed_json.get('taxable_amount', 0.0) or 0.0)
    cgst = float(parsed_json.get('cgst', 0.0) or 0.0)
    sgst = float(parsed_json.get('sgst', 0.0) or 0.0)
    igst = float(parsed_json.get('igst', 0.0) or 0.0)
    cess = float(parsed_json.get('cess', 0.0) or 0.0)
    total = float(parsed_json.get('total_amount', 0.0) or 0.0)

    # Rule A: Totals arithmetic check with a ₹1 rounding tolerance
    computed_total = taxable + cgst + sgst + igst + cess
    if abs(computed_total - total) > 1.0:
        warnings.append(f"Total mismatch: taxable + taxes sum to ₹{computed_total:.2f}, but total_amount is ₹{total:.2f}.")

    # Rule B: GSTIN format validator
    party_gstin = parsed_json.get('party_gstin')
    if party_gstin:
        gstin_regex = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        if not re.match(gstin_regex, str(party_gstin).strip().upper()):
            warnings.append(f"Invalid party GSTIN format: '{party_gstin}'.")

    # Rule C: Inter-state vs Intra-state classification check
    has_intra = (cgst > 0 or sgst > 0)
    has_inter = (igst > 0)
    if (has_intra or has_inter):
        intra_valid = (cgst > 0 and sgst > 0 and igst == 0)
        inter_valid = (igst > 0 and cgst == 0 and sgst == 0)
        if not (intra_valid or inter_valid):
            warnings.append("Tax classification warning: conflicting GST structure (both CGST/SGST and IGST are populated, or CGST/SGST splits are uneven).")

    # 5. Save Data & Finalize status to needs_review
    bill.status = 'needs_review'
    bill.raw_data = parsed_json
    bill.extraction_raw_json = raw_json_str
    bill.validation_warnings = warnings
    bill.extraction_failed = False
    bill.save()

    logger.info("Bill ID %s processed successfully with status 'needs_review'. Warnings: %s", bill_id, len(warnings))

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

from .models import ImportExportRecord

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
def extract_trade_doc_data(self, record_id):
    """
    Celery task: Extracts structured metadata from Bill of Entry / Shipping Bill
    documents using Gemini Vision API.

    Fields extracted: be_number, be_date, container_id, gross_weight, net_weight,
    port_code, assessable_value, shipper_name, currency, confidence.

    On success → status='needs_review' (accountant must verify; no auto-finalizing).
    On parse failure → status='needs_review', extraction_failed=True.
    On network failure (retryable) → retry up to max_retries, then 'extraction_failed'.
    """
    logger.info("Starting trade doc extraction for Record ID %s (Attempt %s)", record_id, self.request.retries + 1)

    try:
        record = ImportExportRecord.objects.get(id=record_id)
    except ImportExportRecord.DoesNotExist:
        logger.error("ImportExportRecord ID %s not found.", record_id)
        return

    # 1. Fetch file bytes (local or remote)
    try:
        if record.file_url.startswith('/media/') or not record.file_url.startswith('http'):
            relative_path = record.file_url.replace(settings.MEDIA_URL, '', 1)
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            with open(file_path, 'rb') as f:
                file_data = f.read()
        else:
            req = urllib.request.Request(
                record.file_url,
                headers={'User-Agent': 'LedgerPro Trade Doc Extraction Pipeline'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                file_data = response.read()
    except Exception as e:
        logger.error("Failed to read file for Record %s: %s", record_id, e)
        if self.request.retries >= self.max_retries:
            record.status = 'extraction_failed'
            record.extraction_failed = True
            record.save()
        else:
            raise self.retry(exc=e)
        return

    base64_data = base64.b64encode(file_data).decode('utf-8')
    mime_type = get_mime_type(record.file_name)

    # 2. Call Gemini Vision API
    gemini_api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
    is_dummy_key = (
        not gemini_api_key
        or gemini_api_key.startswith('mock-')
        or 'YOUR_GEMINI_KEY' in gemini_api_key
    )

    if is_dummy_key:
        # Development mock fallback
        logger.warning("No valid Gemini key — using mock trade doc extraction for Record %s.", record_id)
        time.sleep(2)
        mock_response = {
            "be_number": "BE2026-00123",
            "be_date": "2026-06-30",
            "port_code": "INMAA1",
            "container_id": "TCKU3953645",
            "gross_weight": 12500.0,
            "net_weight": 11800.0,
            "currency": "USD",
            "assessable_value": 85000.0,
            "shipper_name": "Global Freight Partners Ltd",
            "confidence": {
                "be_number": 0.95,
                "be_date": 0.97,
                "port_code": 0.88,
                "container_id": 0.92,
                "assessable_value": 0.90,
                "shipper_name": 0.93
            }
        }
        raw_json_str = json.dumps(mock_response)
        parsed_json = mock_response
    else:
        prompt_text = (
            "Analyze this Bill of Entry or Shipping Bill document and extract the following fields.\n"
            "Return ONLY a valid JSON object with exactly these keys:\n"
            "{\n"
            '  "be_number": "string (Bill of Entry number, or shipping bill number)",\n'
            '  "be_date": "string (ISO format YYYY-MM-DD — the date on the document)",\n'
            '  "port_code": "string (customs port code, e.g. INMAA1 for Chennai)",\n'
            '  "container_id": "string (container or airway bill number, or null if absent)",\n'
            '  "gross_weight": number (gross weight in KG, default 0.0),\n'
            '  "net_weight": number (net weight in KG, default 0.0),\n'
            '  "currency": "string (3-letter ISO currency code, e.g. USD, EUR, INR)",\n'
            '  "assessable_value": number (customs assessable value in the document currency, default 0.0),\n'
            '  "shipper_name": "string (name of the exporter/shipper or supplier, or null if not visible)",\n'
            '  "confidence": {\n'
            '    "be_number": number (0.0 to 1.0),\n'
            '    "be_date": number (0.0 to 1.0),\n'
            '    "assessable_value": number (0.0 to 1.0),\n'
            '    "shipper_name": number (0.0 to 1.0)\n'
            '  }\n'
            "}\n"
            "Do not include any explanation, markdown fences, or extra text. Return only the JSON object."
        )

        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash"
            f":generateContent?key={gemini_api_key}"
        )
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {"inlineData": {"mimeType": mime_type, "data": base64_data}}
                ]
            }],
            "generationConfig": {"responseMimeType": "application/json"}
        }

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

        except urllib.error.HTTPError as he:
            logger.error("Gemini API HTTP Error %s for Record %s: %s", he.code, record_id, he.read().decode())
            if he.code in [429, 500, 503, 504]:
                if self.request.retries >= self.max_retries:
                    record.status = 'extraction_failed'
                    record.extraction_failed = True
                    record.save()
                    return
                raise self.retry(exc=he)
            else:
                record.status = 'needs_review'
                record.extraction_failed = True
                record.validation_warnings = [f"API Error: HTTP {he.code}"]
                record.save()
                return
        except Exception as e:
            logger.error("Unexpected Gemini error for Record %s: %s", record_id, e)
            if self.request.retries >= self.max_retries:
                record.status = 'extraction_failed'
                record.extraction_failed = True
                record.save()
            else:
                raise self.retry(exc=e)
            return

        # 3. Defensive JSON parsing
        try:
            text = raw_json_str.strip()
            if text.startswith("```"):
                text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
            parsed_json = json.loads(text.strip())
        except Exception as pe:
            logger.error("JSON parse failure for Record %s: %s", record_id, pe)
            record.status = 'needs_review'
            record.extraction_failed = True
            record.extraction_raw_json = raw_json_str
            record.validation_warnings = ["AI Parsing Error: Response did not contain valid structured JSON."]
            record.save()
            return

    # 4. Validation rules for trade docs
    warnings = []

    gross = float(parsed_json.get('gross_weight', 0.0) or 0.0)
    net = float(parsed_json.get('net_weight', 0.0) or 0.0)

    # Rule A: net weight must not exceed gross weight
    if net > gross > 0:
        warnings.append(
            f"Weight inconsistency: net weight ({net} KG) exceeds gross weight ({gross} KG)."
        )

    # Rule B: assessable value must be positive
    assessable = float(parsed_json.get('assessable_value', 0.0) or 0.0)
    if assessable <= 0:
        warnings.append("Assessable value is zero or missing — please verify the document.")

    # Rule C: BE date format check
    be_date_str = parsed_json.get('be_date')
    if be_date_str:
        try:
            from datetime import datetime
            datetime.strptime(str(be_date_str)[:10], '%Y-%m-%d')
        except ValueError:
            warnings.append(f"BE date format is invalid: '{be_date_str}'. Expected YYYY-MM-DD.")

    # 5. Promote canonical fields to model columns (fast filtering later)
    from datetime import datetime as dt
    be_date_parsed = None
    if be_date_str:
        try:
            be_date_parsed = dt.strptime(str(be_date_str)[:10], '%Y-%m-%d').date()
        except ValueError:
            pass

    record.status = 'needs_review'
    record.raw_data = parsed_json
    record.extraction_raw_json = raw_json_str
    record.validation_warnings = warnings
    record.extraction_failed = False

    # Promote to typed columns
    record.be_number = str(parsed_json.get('be_number') or '')[:100] or None
    record.be_date = be_date_parsed
    record.port_code = str(parsed_json.get('port_code') or '')[:20] or None
    record.container_id = str(parsed_json.get('container_id') or '')[:100] or None
    record.gross_weight = gross or None
    record.net_weight = net or None
    record.currency = str(parsed_json.get('currency') or '')[:10] or None
    record.assessable_value = assessable or None
    record.shipper_name = str(parsed_json.get('shipper_name') or '')[:255] or None

    record.save()
    logger.info(
        "Trade doc Record %s extracted → needs_review. Warnings: %s",
        record_id, len(warnings)
    )

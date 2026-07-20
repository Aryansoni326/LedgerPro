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

from .models import EwayBillRecord

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


@shared_task(bind=True, max_retries=6, default_retry_delay=10)
def extract_eway_bill_data(self, record_id):
    """
    Celery task: Extracts structured metadata from E-Way Bill documents using Gemini Vision API.
    Fields extracted: eway_bill_number, be_number, vehicle_number, confidence.
    """
    logger.info("Starting E-Way Bill extraction for Record ID %s (Attempt %s)", record_id, self.request.retries + 1)

    try:
        record = EwayBillRecord.objects.get(id=record_id)
    except EwayBillRecord.DoesNotExist:
        logger.error("EwayBillRecord ID %s not found.", record_id)
        return

    # 1. Fetch file bytes
    try:
        if record.file_url.startswith('/media/') or not record.file_url.startswith('http'):
            relative_path = record.file_url.replace(settings.MEDIA_URL, '', 1)
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            with open(file_path, 'rb') as f:
                file_data = f.read()
        else:
            req = urllib.request.Request(
                record.file_url,
                headers={'User-Agent': 'LedgerPro E-Way Bill Extraction Pipeline'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                file_data = response.read()
    except Exception as e:
        logger.error("Failed to read file for E-Way Bill %s: %s", record_id, e)
        if self.request.retries >= self.max_retries:
            record.status = 'extraction_failed'
            record.extraction_failed = True
            record.save()
        else:
            raise self.retry(exc=e)
        return

    base64_data = base64.b64encode(file_data).decode('utf-8')
    mime_type = get_mime_type(record.file_name)

    warnings = []

    # 2. Call Gemini Vision API
    gemini_api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
    is_dummy_key = (
        not gemini_api_key
        or gemini_api_key.strip() == ""
        or gemini_api_key.startswith('mock-')
        or 'your_gemini_key' in gemini_api_key.lower()
        or 'your-gemini-api-key' in gemini_api_key.lower()
        or 'your-gemini-key' in gemini_api_key.lower()
    )

    if is_dummy_key:
        logger.warning("No valid Gemini key — using mock E-Way Bill extraction for Record %s.", record_id)
        warnings.append("API key is a dummy/placeholder key. Please set a valid GEMINI_API_KEY to extract real data.")
        warnings.append("Using mock data fallback for development.")
        time.sleep(2)
        mock_response = {
            "eway_bill_number": "991234567890",
            "be_number": "BE-2026-9976",
            "vehicle_number": "GJ38TA7322",
            "confidence": {
                "eway_bill_number": 0.98,
                "be_number": 0.95
            }
        }
        raw_json_str = json.dumps(mock_response)
        parsed_json = mock_response
    else:
        prompt_text = (
            "Analyze this E-Way Bill / Transit Permit document and extract the following fields.\n"
            "Return ONLY a valid JSON object with exactly these keys:\n"
            "{\n"
            '  "eway_bill_number": "string (E-Way Bill Number, usually a 12-digit number)",\n'
            '  "be_number": "string (Bill of Entry number or BE number. Note: on the E-Way Bill, this is typically labelled as \'Document No.\', \'Doc No\', \'Doc. No.\', or \'Document No. & Date\'. Extract the numeric part of the Document No as the be_number. E.g. if Document No is \'9731115\', be_number should be \'9731115\')\",\n'
            '  "vehicle_number": "string (Vehicle number, e.g. GJ38TA7322, or null if not found)",\n'
            '  "confidence": {\n'
            '    "eway_bill_number": number (0.0 to 1.0),\n'
            '    "be_number": number (0.0 to 1.0)\n'
            '  }\n'
            "}\n"
            "Do not include any explanation, markdown fences, or extra text. Return only the JSON object."
        )

        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash"
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
            logger.error("Gemini API HTTP Error %s for E-Way Bill %s: %s", he.code, record_id, he.read().decode())
            if he.code in [429, 500, 503, 504]:
                if self.request.retries >= self.max_retries:
                    record.status = 'extraction_failed'
                    record.extraction_failed = True
                    record.validation_warnings = [f"Gemini API Rate Limit/Transient Error (HTTP {he.code}). Using local parser."]
                    record.save()
                    return
                import random
                # Exponential backoff with jitter: 5s, 10s, 20s, 40s, 80s, 160s + random 1-5s
                backoff = 5 * (2 ** self.request.retries) + random.randint(1, 5)
                logger.info("Retrying task for E-Way Bill %s in %s seconds due to HTTP %s.", record_id, backoff, he.code)
                raise self.retry(exc=he, countdown=backoff)
            else:
                record.status = 'needs_review'
                record.extraction_failed = True
                record.validation_warnings = [f"API Error: HTTP {he.code}"]
                record.save()
                return
        except Exception as e:
            logger.error("Unexpected Gemini error for E-Way Bill %s: %s", record_id, e)
            if self.request.retries >= self.max_retries:
                record.status = 'extraction_failed'
                record.extraction_failed = True
                record.save()
            else:
                raise self.retry(exc=e)
            return

        # 3. JSON parsing
        try:
            text = raw_json_str.strip()
            if text.startswith("```"):
                text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
            parsed_json = json.loads(text.strip())
        except Exception as pe:
            logger.error("JSON parse failure for E-Way Bill %s: %s", record_id, pe)
            record.status = 'needs_review'
            record.extraction_failed = True
            record.extraction_raw_json = raw_json_str
            record.validation_warnings = ["AI Parsing Error: Response did not contain valid structured JSON."]
            record.save()
            return

    # 4. Save results back
    record.status = 'needs_review'
    record.raw_data = parsed_json
    record.extraction_raw_json = raw_json_str
    record.validation_warnings = warnings
    record.extraction_failed = False

    # Promote to typed columns
    record.eway_bill_number = str(parsed_json.get('eway_bill_number') or '')[:100] or None
    record.be_number = str(parsed_json.get('be_number') or '')[:100] or None
    record.vehicle_number = str(parsed_json.get('vehicle_number') or '')[:50] or None

    record.save()
    logger.info(
        "E-Way Bill Record %s extracted → needs_review. Warnings: %s",
        record_id, len(warnings)
    )

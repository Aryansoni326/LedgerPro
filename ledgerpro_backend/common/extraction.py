"""
Shared extraction infrastructure for the LedgerPro document pipeline.

Every Celery extraction task (invoices, trade_docs, eway_bills, intelligence)
delegates file-fetching, Gemini API calls, and response parsing to these
helpers so the logic lives in one place.
"""
import base64
import json
import logging
import os
import random
import re
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def get_mime_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
    }.get(ext, 'application/octet-stream')


def fetch_file_bytes(file_url: str, user_agent: str = 'LedgerPro Extraction Pipeline') -> bytes:
    """Download file bytes from a local media path or remote URL."""
    if file_url.startswith('/media/') or not file_url.startswith('http'):
        relative_path = file_url.replace(settings.MEDIA_URL, '', 1)
        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        with open(file_path, 'rb') as f:
            return f.read()

    req = urllib.request.Request(file_url, headers={'User-Agent': user_agent})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read()


# ---------------------------------------------------------------------------
# Gemini Vision API
# ---------------------------------------------------------------------------

def is_dummy_api_key(key: str | None) -> bool:
    if not key or key.strip() == '':
        return True
    lower = key.lower()
    return (
        key.startswith('mock-')
        or 'your_gemini_key' in lower
        or 'your-gemini-api-key' in lower
        or 'your-gemini-key' in lower
    )


def call_gemini_vision(
    *,
    prompt_text: str,
    base64_data: str,
    mime_type: str,
    api_key: str,
    model: str = 'gemini-2.5-flash',
    timeout: int = 30,
) -> str:
    """Call Gemini Vision API and return the raw text from the first candidate.

    Raises ``urllib.error.HTTPError`` on API errors and ``Exception`` on
    unexpected failures — callers handle retry logic.
    """
    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    payload = {
        'contents': [{
            'parts': [
                {'text': prompt_text},
                {'inlineData': {'mimeType': mime_type, 'data': base64_data}},
            ],
        }],
        'generationConfig': {'responseMimeType': 'application/json'},
    }
    req = urllib.request.Request(
        api_url,
        headers={'Content-Type': 'application/json'},
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        response_data = json.loads(res.read().decode())

    return response_data['candidates'][0]['content']['parts'][0]['text']


def parse_gemini_response(raw_text: str) -> dict:
    """Strip markdown fences and parse JSON from a Gemini response string."""
    text = raw_text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return json.loads(text.strip())


def exponential_backoff(retries: int) -> int:
    """5 * 2^retries + random jitter, matching existing task pattern."""
    return 5 * (2 ** retries) + random.randint(1, 5)

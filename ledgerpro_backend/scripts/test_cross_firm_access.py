#!/usr/bin/env python
"""
Standalone script to verify firm-level data isolation returns HTTP 403.

Usage:
    cd ledgerpro_backend
    python scripts/test_cross_firm_access.py

Exits 0 when all probes return 403.
Exits 1 if any probe allows cross-firm access (non-403).
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

# Ensure ledgerpro_backend is on sys.path when run as a script
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ledgerpro_backend.settings')
os.environ.setdefault('USE_SQLITE', 'True')
django.setup()

from django.conf import settings  # noqa: E402

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.core import signing  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from accounts.models import User  # noqa: E402
from firms.models import Firm  # noqa: E402
from invoices.models import Bill  # noqa: E402
from trade_docs.models import ImportExportRecord  # noqa: E402
from vault.models import CloudVaultEntry  # noqa: E402


def auth_token(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp_timestamp': (timezone.now() + timedelta(days=7)).timestamp(),
    }
    return signing.dumps(payload, key=settings.SECRET_KEY)


def main():
    User.objects.filter(email__in=['probe-a@test.com', 'probe-b@test.com']).delete()

    user_a = User.objects.create_user(username='probe-a@test.com', email='probe-a@test.com')
    user_b = User.objects.create_user(username='probe-b@test.com', email='probe-b@test.com')

    firm_b = Firm.objects.create(
        name='Probe B Corp',
        state='Gujarat',
        city='Ahmedabad',
        owner_email='owner-b@probe.com',
        created_by=user_b,
        status='active',
    )
    bill_b = Bill.objects.create(
        firm=firm_b,
        file_name='secret.pdf',
        file_url='/media/secret.pdf',
        file_size=50,
        uploaded_by=user_b,
    )
    trade_b = ImportExportRecord.objects.create(
        firm=firm_b,
        file_name='secret_be.pdf',
        file_url='/media/secret_be.pdf',
        file_size=50,
        uploaded_by=user_b,
    )
    vault_b = CloudVaultEntry.objects.create(
        firm=firm_b,
        bill=bill_b,
        file_name='secret.pdf',
        file_url='/media/secret.pdf',
        module='invoices',
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token(user_a)}')

    probes = [
        ('GET', f'/api/firms/{firm_b.id}/invoices', None),
        ('GET', f'/api/firms/{firm_b.id}/trade-docs', None),
        ('GET', f'/api/firms/{firm_b.id}/vault/years', None),
        ('GET', f'/api/firms/{firm_b.id}/analytics/summary?range=year', None),
        ('PATCH', f'/api/invoices/{bill_b.id}', {'raw_data': {'invoice_number': 'X'}}),
        ('DELETE', f'/api/invoices/{bill_b.id}', None),
        ('POST', f'/api/invoices/{bill_b.id}/verify', None),
        ('GET', f'/api/trade-docs/{trade_b.id}', None),
        ('DELETE', f'/api/vault/{vault_b.id}', None),
    ]

    failures = []
    print('Cross-firm access probe (user A -> user B resources)\n' + '-' * 50)

    for method, path, body in probes:
        if method == 'GET':
            resp = client.get(path)
        elif method == 'PATCH':
            resp = client.patch(path, body, format='json')
        elif method == 'DELETE':
            resp = client.delete(path)
        elif method == 'POST':
            resp = client.post(path, body or {}, format='json')
        else:
            continue

        ok = resp.status_code == 403
        status_label = 'PASS' if ok else 'FAIL'
        print(f'[{status_label}] {method} {path} -> {resp.status_code}')
        if not ok:
            failures.append((method, path, resp.status_code, resp.content[:200]))

    print('-' * 50)
    if failures:
        print(f'\n{len(failures)} probe(s) did NOT return 403:')
        for method, path, code, body in failures:
            print(f'  {method} {path}: HTTP {code} {body!r}')
        sys.exit(1)

    print('\nAll probes returned 403 — firm isolation OK.')
    sys.exit(0)


if __name__ == '__main__':
    main()

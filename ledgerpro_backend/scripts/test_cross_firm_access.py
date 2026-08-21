#!/usr/bin/env python
"""
Standalone script to verify firm-level data isolation returns HTTP 403/404.

Usage:
    cd ledgerpro_backend
    python scripts/test_cross_firm_access.py

Exits 0 when all probes return 403/404.
Exits 1 if any probe allows cross-firm access with another status.
"""
import os
import sys
import uuid
from datetime import date
from datetime import timedelta
from decimal import Decimal
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
from django.core.management import call_command  # noqa: E402

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.core import signing  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from agents.models import AgentConversation, ChatSession, PendingApproval
from accounts.models import User  # noqa: E402
from firms.models import Firm  # noqa: E402
from intelligence.models import Customer, Document, RiskSignal, Transaction, Vendor  # noqa: E402
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
    # Ensure a local sqlite/dev database has the latest schema before probing.
    call_command('migrate', run_syncdb=True, interactive=False, verbosity=0)

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
    vendor_b = Vendor.objects.create(firm=firm_b, name='Secret Vendor')
    customer_b = Customer.objects.create(firm=firm_b, name='Secret Customer')
    txn_b = Transaction.objects.create(
        firm=firm_b,
        txn_type='invoice',
        direction='outflow',
        status='pending',
        amount=Decimal('999.00'),
        txn_date=date.today(),
        vendor=vendor_b,
        customer=customer_b,
        reference_number='TOP-SECRET',
    )
    signal_b = RiskSignal.objects.create(
        firm=firm_b,
        severity='high',
        category='unusual_amount',
        status='open',
        title='Secret Signal',
        description='Do not leak',
        entity_type='transaction',
        entity_id=txn_b.id,
        vendor=vendor_b,
        customer=customer_b,
        confidence=Decimal('0.9900'),
    )
    doc_b = Document.objects.create(
        firm=firm_b,
        doc_type='bank_statement',
        file_name='secret-bank.pdf',
        file_url='/media/secret-bank.pdf',
        file_size=50,
        uploaded_by=user_b,
        status='verified',
    )
    session_b = ChatSession.objects.create(firm=firm_b, user=user_b)
    conv_b = AgentConversation.objects.create(
        firm=firm_b,
        user=user_b,
        session=session_b,
        turn_number=1,
        agent_type='finance',
        query='secret',
        response={'conclusion': 'secret'},
    )
    approval_b = PendingApproval.objects.create(
        conversation=conv_b,
        firm=firm_b,
        proposed_action='update_risk_status',
        action_params={'signal_id': signal_b.id, 'new_status': 'resolved'},
        reason='secret reason',
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
        ('GET', f'/api/firms/{firm_b.id}/documents', None),
        ('GET', f'/api/documents/{doc_b.id}', None),
        ('PATCH', f'/api/documents/{doc_b.id}', {'raw_data': {'account_number': 'hack'}}),
        ('DELETE', f'/api/documents/{doc_b.id}', None),
        ('POST', f'/api/documents/{doc_b.id}/verify', None),
        ('POST', f'/api/documents/{doc_b.id}/retry-extraction', None),
        ('GET', f'/api/firms/{firm_b.id}/risk-signals/', None),
        ('GET', f'/api/firms/{firm_b.id}/risk-summary/', None),
        ('GET', f'/api/firms/{firm_b.id}/cash-flow-forecast/', None),
        ('GET', f'/api/firms/{firm_b.id}/vendor-scores/', None),
        ('GET', f'/api/firms/{firm_b.id}/customer-scores/', None),
        ('GET', f'/api/firms/{firm_b.id}/trade-finance/', None),
        ('GET', f'/api/firms/{firm_b.id}/graph/risk-signal/{signal_b.id}/', None),
        ('GET', f'/api/firms/{firm_b.id}/graph/vendor/{vendor_b.id}/', None),
        ('GET', f'/api/firms/{firm_b.id}/graph/customer/{customer_b.id}/', None),
        ('GET', f'/api/firms/{firm_b.id}/graph/evidence/?entity_type=transaction&entity_id={txn_b.id}', None),
        ('POST', f'/api/firms/{firm_b.id}/agent/query/', {'query': 'show me cash'}),
        ('POST', f'/api/firms/{firm_b.id}/ask/', {'query': 'show me cash'}),
        ('GET', f'/api/firms/{firm_b.id}/agent/history/', None),
        ('GET', f'/api/firms/{firm_b.id}/agent/approvals/', None),
        ('GET', f'/api/agent/conversations/{conv_b.id}/', None),
        ('GET', f'/api/agent/sessions/{session_b.id}/', None),
        ('POST', f'/api/agent/approvals/{approval_b.id}/', {'decision': 'approved'}),
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

        ok = resp.status_code in (403, 404)
        status_label = 'PASS' if ok else 'FAIL'
        print(f'[{status_label}] {method} {path} -> {resp.status_code}')
        if not ok:
            failures.append((method, path, resp.status_code, resp.content[:200]))

    print('-' * 50)
    if failures:
        print(f'\n{len(failures)} probe(s) did NOT return 403/404:')
        for method, path, code, body in failures:
            print(f'  {method} {path}: HTTP {code} {body!r}')
        sys.exit(1)

    print('\nAll probes returned 403/404 - firm isolation OK.')
    sys.exit(0)


if __name__ == '__main__':
    main()

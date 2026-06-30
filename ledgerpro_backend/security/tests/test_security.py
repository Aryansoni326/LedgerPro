"""
Cross-firm access isolation test suite.

Run:
    cd ledgerpro_backend
    python manage.py test security.tests.test_cross_firm_isolation security.tests.test_otp_security security.tests.test_upload_validation
"""
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from accounts.services import OTPService
from eway_bills.models import EwayBillRecord
from firms.models import Firm
from invoices.models import Bill
from trade_docs.models import ImportExportRecord
from vault.models import CloudVaultEntry


def _auth_token(user: User) -> str:
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp_timestamp': (timezone.now() + timedelta(days=7)).timestamp(),
    }
    return signing.dumps(payload, key=settings.SECRET_KEY)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class CrossFirmIsolationTests(TestCase):
    """Verify accountants cannot access another accountant's firm data."""

    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()

        self.user_a = User.objects.create_user(
            username='alice@firm.com', email='alice@firm.com', password='unused'
        )
        self.user_b = User.objects.create_user(
            username='bob@firm.com', email='bob@firm.com', password='unused'
        )

        self.firm_a = Firm.objects.create(
            name='Alice Corp',
            state='Maharashtra',
            city='Mumbai',
            owner_email='owner-a@corp.com',
            created_by=self.user_a,
            status='active',
        )
        self.firm_b = Firm.objects.create(
            name='Bob Corp',
            state='Karnataka',
            city='Bengaluru',
            owner_email='owner-b@corp.com',
            created_by=self.user_b,
            status='active',
        )

        self.bill_a = Bill.objects.create(
            firm=self.firm_a,
            file_name='invoice_a.pdf',
            file_url='/media/a.pdf',
            file_size=100,
            uploaded_by=self.user_a,
        )
        self.bill_b = Bill.objects.create(
            firm=self.firm_b,
            file_name='invoice_b.pdf',
            file_url='/media/b.pdf',
            file_size=100,
            uploaded_by=self.user_b,
        )

        self.trade_a = ImportExportRecord.objects.create(
            firm=self.firm_a,
            file_name='be_a.pdf',
            file_url='/media/be_a.pdf',
            file_size=100,
            uploaded_by=self.user_a,
        )
        self.trade_b = ImportExportRecord.objects.create(
            firm=self.firm_b,
            file_name='be_b.pdf',
            file_url='/media/be_b.pdf',
            file_size=100,
            uploaded_by=self.user_b,
        )

        self.eway_a = EwayBillRecord.objects.create(
            firm=self.firm_a,
            file_name='eway_a.pdf',
            file_url='/media/eway_a.pdf',
            file_size=100,
            uploaded_by=self.user_a,
        )

        self.vault_a = CloudVaultEntry.objects.create(
            firm=self.firm_a,
            bill=self.bill_a,
            file_name='invoice_a.pdf',
            file_url='/media/a.pdf',
            module='invoices',
        )
        self.vault_b = CloudVaultEntry.objects.create(
            firm=self.firm_b,
            bill=self.bill_b,
            file_name='invoice_b.pdf',
            file_url='/media/b.pdf',
            module='invoices',
        )

        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_a)}')
        self.client_b.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_b)}')

    def test_cross_firm_invoice_list_returns_403(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_b.id}/invoices')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_analytics_returns_403(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_b.id}/analytics/summary?range=year')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_vault_returns_403(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_b.id}/vault/years')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_trade_docs_returns_403(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_b.id}/trade-docs')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_bill_by_id_returns_403(self):
        resp = self.client_a.patch(
            f'/api/invoices/{self.bill_b.id}',
            {'raw_data': {'invoice_number': 'HACK'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_bill_delete_returns_403(self):
        resp = self.client_a.delete(f'/api/invoices/{self.bill_b.id}')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_bill_verify_returns_403(self):
        resp = self.client_a.post(f'/api/invoices/{self.bill_b.id}/verify')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_trade_doc_returns_403(self):
        resp = self.client_a.get(f'/api/trade-docs/{self.trade_b.id}')
        self.assertEqual(resp.status_code, 403)

    def test_cross_firm_vault_entry_delete_returns_403(self):
        resp = self.client_a.delete(f'/api/vault/{self.vault_b.id}')
        self.assertEqual(resp.status_code, 403)

    def test_own_firm_access_succeeds(self):
        resp = self.client_a.get(f'/api/firms/{self.firm_a.id}/invoices')
        self.assertEqual(resp.status_code, 200)


@override_settings(USE_SQLITE=True)
class OTPSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='otp@test.com', email='otp@test.com', password='unused'
        )
        self.client = APIClient()

    def _create_session(self):
        verification, code = OTPService.create_verification(user=self.user)
        return verification, code

    def test_lockout_after_five_wrong_attempts(self):
        verification, _correct = self._create_session()
        for i in range(5):
            resp = self.client.post(
                '/api/auth/otp/verify',
                {'pending_token': verification.pending_token, 'code': '0000'},
                format='json',
            )
            self.assertEqual(resp.status_code, 400, msg=f'attempt {i + 1}')

        verification.refresh_from_db()
        self.assertTrue(verification.is_locked)

        resp = self.client.post(
            '/api/auth/otp/verify',
            {'pending_token': verification.pending_token, 'code': '0000'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('locked', resp.json()['error'].lower())

    def test_correct_code_after_failures_still_locked(self):
        verification, code = self._create_session()
        for _ in range(5):
            self.client.post(
                '/api/auth/otp/verify',
                {'pending_token': verification.pending_token, 'code': '0000'},
                format='json',
            )
        resp = self.client.post(
            '/api/auth/otp/verify',
            {'pending_token': verification.pending_token, 'code': code},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_ip_rate_limit_on_verify(self):
        verification, _ = self._create_session()
        for _ in range(15):
            self.client.post(
                '/api/auth/otp/verify',
                {'pending_token': verification.pending_token, 'code': '0000'},
                format='json',
                REMOTE_ADDR='10.0.0.99',
            )
        resp = self.client.post(
            '/api/auth/otp/verify',
            {'pending_token': verification.pending_token, 'code': '0000'},
            format='json',
            REMOTE_ADDR='10.0.0.99',
        )
        self.assertEqual(resp.status_code, 429)


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class UploadValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='upload@test.com', email='upload@test.com', password='unused'
        )
        self.firm = Firm.objects.create(
            name='Upload Test',
            state='Delhi',
            city='Delhi',
            owner_email='owner@upload.com',
            created_by=self.user,
            status='active',
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user)}')

    def test_rejects_executable_disguised_as_pdf(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile(
            'malware.pdf',
            b'#!/bin/bash\necho pwned',
            content_type='application/pdf',
        )
        resp = self.client.post(
            f'/api/firms/{self.firm.id}/invoices/upload',
            {'files': fake_pdf},
            format='multipart',
        )
        self.assertIn(resp.status_code, (400, 201))
        if resp.status_code == 201:
            self.assertTrue(resp.json().get('errors'))
        else:
            self.assertTrue(resp.json().get('errors') or resp.json().get('error'))

    def test_accepts_valid_pdf_magic_bytes(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        valid_pdf = SimpleUploadedFile(
            'real.pdf',
            b'%PDF-1.4 minimal test content',
            content_type='application/pdf',
        )
        resp = self.client.post(
            f'/api/firms/{self.firm.id}/invoices/upload',
            {'files': valid_pdf},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['uploaded'])

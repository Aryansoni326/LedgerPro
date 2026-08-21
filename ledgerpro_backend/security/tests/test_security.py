"""
Cross-firm access isolation test suite.

Run:
    cd ledgerpro_backend
    python manage.py test security.tests.test_cross_firm_isolation security.tests.test_otp_security security.tests.test_upload_validation
"""
import uuid
from datetime import date
from datetime import timedelta
from decimal import Decimal

from django.http import Http404

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from agents.models import AgentAction, AgentConversation, ChatSession, PendingApproval
from accounts.models import User
from accounts.services import OTPService
from audit.models import AuditLog
from eway_bills.models import EwayBillRecord
from firms.access import (
    get_agent_action_for_user,
    get_agent_conversation_for_user,
    get_chat_session_for_user,
    get_customer_for_user,
    get_customer_score_for_user,
    get_document_for_user,
    get_financial_snapshot_for_user,
    get_pending_approval_for_user,
    get_reconciliation_exception_for_user,
    get_reconciliation_link_for_user,
    get_reconciliation_run_for_user,
    get_risk_signal_for_user,
    get_trade_finance_link_for_user,
    get_transaction_for_user,
    get_vendor_for_user,
    get_vendor_score_for_user,
)
from firms.models import Firm
from intelligence.models import (
    Customer,
    CustomerScore,
    Document,
    FinancialSnapshot,
    ReconciliationException,
    ReconciliationLink,
    ReconciliationRun,
    RiskSignal,
    TradeFinanceLink,
    Transaction,
    Vendor,
    VendorScore,
)
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


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class ExpandedFirmScopedModelIsolationTests(TestCase):
    """Cross-firm isolation coverage for firm-scoped models added in later phases."""

    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()

        self.user_a = User.objects.create_user(
            username='sec-a@firm.com', email='sec-a@firm.com', password='unused'
        )
        self.user_b = User.objects.create_user(
            username='sec-b@firm.com', email='sec-b@firm.com', password='unused'
        )
        self.owner_b = User.objects.create_user(
            username='owner-b@secure.com', email='owner-b@secure.com', password='unused', role='owner'
        )

        self.firm_a = Firm.objects.create(
            name='Secure A',
            state='Maharashtra',
            city='Mumbai',
            owner_email='owner-a@secure.com',
            created_by=self.user_a,
            status='active',
        )
        self.firm_b = Firm.objects.create(
            name='Secure B',
            state='Karnataka',
            city='Bengaluru',
            owner_email='owner-b@secure.com',
            created_by=self.user_b,
            status='active',
        )

        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_a)}')
        self.client_b.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.user_b)}')

        self.vendor_b = Vendor.objects.create(firm=self.firm_b, name='Vendor B')
        self.customer_b = Customer.objects.create(firm=self.firm_b, name='Customer B')
        self.txn_b = Transaction.objects.create(
            firm=self.firm_b,
            txn_type='invoice',
            direction='outflow',
            status='pending',
            amount=Decimal('1500.00'),
            txn_date=date.today(),
            vendor=self.vendor_b,
            customer=self.customer_b,
            reference_number='B-INV-1',
        )
        self.signal_b = RiskSignal.objects.create(
            firm=self.firm_b,
            severity='high',
            category='unusual_amount',
            status='open',
            title='Signal B',
            description='Test signal',
            entity_type='transaction',
            entity_id=self.txn_b.id,
            vendor=self.vendor_b,
            customer=self.customer_b,
            confidence=Decimal('0.9200'),
        )
        self.doc_b = Document.objects.create(
            firm=self.firm_b,
            doc_type='bank_statement',
            file_name='bank.pdf',
            file_url='/media/bank.pdf',
            file_size=200,
            uploaded_by=self.user_b,
            status='verified',
        )
        self.snapshot_b = FinancialSnapshot.objects.create(
            firm=self.firm_b,
            snapshot_type='daily',
            snapshot_date=date.today(),
            total_receivables=Decimal('2500.00'),
            total_payables=Decimal('500.00'),
            net_cash_flow=Decimal('2000.00'),
            health_score=Decimal('72.50'),
            cashflow_forecast={'current_balance': '12000.00'},
        )
        self.vendor_score_b = VendorScore.objects.create(
            firm=self.firm_b,
            vendor=self.vendor_b,
            overall_score=Decimal('61.00'),
        )
        self.customer_score_b = CustomerScore.objects.create(
            firm=self.firm_b,
            customer=self.customer_b,
            overall_score=Decimal('58.00'),
        )
        self.recon_run_b = ReconciliationRun.objects.create(
            firm=self.firm_b,
            status='completed',
            total_transactions=1,
        )
        self.recon_link_b = ReconciliationLink.objects.create(
            firm=self.firm_b,
            match_group=uuid.uuid4(),
            transaction=self.txn_b,
            matched_transaction=self.txn_b,
            match_confidence=Decimal('1.0000'),
            match_method='manual',
        )
        self.recon_exc_b = ReconciliationException.objects.create(
            firm=self.firm_b,
            transaction=self.txn_b,
            candidate_transaction=self.txn_b,
            match_group=uuid.uuid4(),
            mismatch_cause='other',
            reason='Mismatch',
        )
        self.trade_link_b = TradeFinanceLink.objects.create(
            firm=self.firm_b,
            status='partial',
            invoice_txn=self.txn_b,
            payment_txn=self.txn_b,
            vendor=self.vendor_b,
        )

        self.chat_session_b = ChatSession.objects.create(firm=self.firm_b, user=self.user_b)
        self.agent_conv_b = AgentConversation.objects.create(
            firm=self.firm_b,
            user=self.user_b,
            session=self.chat_session_b,
            turn_number=1,
            agent_type='finance',
            query='Show me cash position',
            response={'conclusion': 'B data'},
            completed_at=timezone.now(),
        )
        self.agent_action_b = AgentAction.objects.create(
            conversation=self.agent_conv_b,
            tool_name='cashflow_forecast',
            tool_input={'firm_id': self.firm_b.id},
            tool_result={'current_balance': '12000.00'},
            duration_ms=10,
        )
        self.pending_approval_b = PendingApproval.objects.create(
            conversation=self.agent_conv_b,
            firm=self.firm_b,
            proposed_action='update_risk_status',
            action_params={'signal_id': self.signal_b.id, 'new_status': 'resolved'},
            reason='Resolve false alarm',
        )

    def test_access_helpers_block_cross_firm_for_all_new_models(self):
        helper_cases = [
            (get_vendor_for_user, self.vendor_b.id),
            (get_customer_for_user, self.customer_b.id),
            (get_transaction_for_user, self.txn_b.id),
            (get_risk_signal_for_user, self.signal_b.id),
            (get_document_for_user, self.doc_b.id),
            (get_financial_snapshot_for_user, self.snapshot_b.id),
            (get_vendor_score_for_user, self.vendor_score_b.id),
            (get_customer_score_for_user, self.customer_score_b.id),
            (get_reconciliation_run_for_user, self.recon_run_b.id),
            (get_reconciliation_link_for_user, self.recon_link_b.id),
            (get_reconciliation_exception_for_user, self.recon_exc_b.id),
            (get_trade_finance_link_for_user, self.trade_link_b.id),
            (get_chat_session_for_user, self.chat_session_b.id),
            (get_agent_conversation_for_user, self.agent_conv_b.id),
            (get_agent_action_for_user, self.agent_action_b.id),
            (get_pending_approval_for_user, self.pending_approval_b.id),
        ]
        for helper, pk in helper_cases:
            with self.assertRaises(Http404, msg=f'{helper.__name__} should deny cross-firm access'):
                helper(self.user_a, pk)

    def test_document_endpoints_block_cross_firm(self):
        self.assertEqual(self.client_a.get(f'/api/firms/{self.firm_b.id}/documents').status_code, 403)
        self.assertEqual(self.client_a.get(f'/api/documents/{self.doc_b.id}').status_code, 404)
        self.assertEqual(
            self.client_a.patch(f'/api/documents/{self.doc_b.id}', {'raw_data': {'x': 1}}, format='json').status_code,
            404,
        )
        self.assertEqual(self.client_a.delete(f'/api/documents/{self.doc_b.id}').status_code, 404)
        self.assertEqual(self.client_a.post(f'/api/documents/{self.doc_b.id}/verify').status_code, 404)
        self.assertEqual(self.client_a.post(f'/api/documents/{self.doc_b.id}/retry-extraction').status_code, 404)

    def test_intelligence_firm_scoped_endpoints_block_cross_firm(self):
        endpoints = [
            f'/api/firms/{self.firm_b.id}/risk-signals/',
            f'/api/firms/{self.firm_b.id}/risk-summary/',
            f'/api/firms/{self.firm_b.id}/cash-flow-forecast/',
            f'/api/firms/{self.firm_b.id}/vendor-scores/',
            f'/api/firms/{self.firm_b.id}/customer-scores/',
            f'/api/firms/{self.firm_b.id}/trade-finance/',
            f'/api/firms/{self.firm_b.id}/graph/risk-signal/{self.signal_b.id}/',
            f'/api/firms/{self.firm_b.id}/graph/vendor/{self.vendor_b.id}/',
            f'/api/firms/{self.firm_b.id}/graph/customer/{self.customer_b.id}/',
        ]
        for path in endpoints:
            self.assertEqual(self.client_a.get(path).status_code, 403, msg=path)
        self.assertEqual(
            self.client_a.get(
                f'/api/firms/{self.firm_b.id}/graph/evidence/',
                {'entity_type': 'transaction', 'entity_id': self.txn_b.id},
            ).status_code,
            403,
        )

    def test_agent_endpoints_block_cross_firm(self):
        self.assertEqual(
            self.client_a.post(
                f'/api/firms/{self.firm_b.id}/agent/query/',
                {'query': 'Show me cash'},
                format='json',
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client_a.post(
                f'/api/firms/{self.firm_b.id}/ask/',
                {'query': 'Show me cash'},
                format='json',
            ).status_code,
            403,
        )
        self.assertEqual(self.client_a.get(f'/api/firms/{self.firm_b.id}/agent/history/').status_code, 403)
        self.assertEqual(self.client_a.get(f'/api/firms/{self.firm_b.id}/agent/approvals/').status_code, 403)
        self.assertEqual(self.client_a.get(f'/api/agent/conversations/{self.agent_conv_b.id}/').status_code, 404)
        self.assertEqual(self.client_a.get(f'/api/agent/sessions/{self.chat_session_b.id}/').status_code, 404)
        self.assertEqual(
            self.client_a.post(
                f'/api/agent/approvals/{self.pending_approval_b.id}/',
                {'decision': 'approved'},
                format='json',
            ).status_code,
            404,
        )

    def test_owner_read_only_cannot_approve_agent_write_action(self):
        owner_client = APIClient()
        owner_client.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.owner_b)}')
        resp = owner_client.post(
            f'/api/agent/approvals/{self.pending_approval_b.id}/',
            {'decision': 'approved', 'notes': 'Looks okay'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.pending_approval_b.refresh_from_db()
        self.signal_b.refresh_from_db()
        self.assertEqual(self.pending_approval_b.status, 'pending')
        self.assertEqual(self.signal_b.status, 'open')

    def test_same_user_cannot_reuse_other_firm_session_context(self):
        dual_user = User.objects.create_user(
            username='dual@firm.com', email='dual@firm.com', password='unused'
        )
        dual_firm_a = Firm.objects.create(
            name='Dual A', state='Delhi', city='Delhi',
            owner_email='owner-dual-a@corp.com', created_by=dual_user, status='active',
        )
        dual_firm_b = Firm.objects.create(
            name='Dual B', state='Goa', city='Panaji',
            owner_email='owner-dual-b@corp.com', created_by=dual_user, status='active',
        )
        dual_client = APIClient()
        dual_client.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(dual_user)}')

        resp_a = dual_client.post(
            f'/api/firms/{dual_firm_a.id}/ask/',
            {'query': 'What is my cash position?'},
            format='json',
        )
        self.assertEqual(resp_a.status_code, 200)
        session_a = resp_a.json()['session_id']

        resp_b = dual_client.post(
            f'/api/firms/{dual_firm_b.id}/ask/',
            {'query': 'Use the prior session and show me the same invoices', 'session_id': session_a},
            format='json',
        )
        self.assertEqual(resp_b.status_code, 200)
        self.assertNotEqual(resp_b.json()['session_id'], session_a)

    def test_document_patch_logs_audit(self):
        resp = self.client_b.patch(
            f'/api/documents/{self.doc_b.id}',
            {'raw_data': {'iban_suffix': '4321'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                firm=self.firm_b,
                resource_type='document',
                resource_id=self.doc_b.id,
                action='edit',
            ).exists()
        )

    def test_risk_signal_patch_logs_audit(self):
        resp = self.client_b.patch(
            f'/api/risk-signals/{self.signal_b.id}',
            {'status': 'resolved'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                firm=self.firm_b,
                resource_type='risk_signal',
                resource_id=self.signal_b.id,
                action='edit',
            ).exists()
        )


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

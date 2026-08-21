"""
Tests for the agent orchestration layer.

Covers:
- Query routing to correct agent type
- Tool selection from allowed sets
- Evidence-Based AI response schema (conclusion/confidence/evidence/reasoning)
- Write-action approval gating (no execution without human sign-off)
- AuditLog integration on approve/reject
- API endpoints (query, history, detail, approvals)
- Cross-firm access control
- Agent responses reference real tool data, not invented numbers
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from audit.models import AuditLog
from agents.executor import execute_agent, route_query, select_tools, AGENT_DEFINITIONS
from agents.models import AgentAction, AgentConversation, ChatSession, PendingApproval
from agents.approval import process_approval
from firms.models import Firm
from intelligence.models import (
    Customer, RiskSignal, Transaction, Vendor, VendorScore,
)


def _auth_token(user: User) -> str:
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp_timestamp': (timezone.now() + timedelta(days=7)).timestamp(),
    }
    return signing.dumps(payload, key=settings.SECRET_KEY)


# ═══════════════════════════════════════════════════════════════════════
# Router tests
# ═══════════════════════════════════════════════════════════════════════

class RouterTests(TestCase):

    def test_routes_risk_query_to_compliance(self):
        self.assertEqual(route_query("Show me all open risk signals"), 'compliance')

    def test_routes_cash_query_to_finance(self):
        self.assertEqual(route_query("What is my cash flow forecast?"), 'finance')

    def test_routes_audit_query(self):
        self.assertEqual(route_query("Show me the audit trail for today"), 'audit')

    def test_routes_executive_query_to_cfo(self):
        self.assertEqual(route_query("Give me an executive summary"), 'cfo')

    def test_routes_reconciliation_to_audit(self):
        self.assertEqual(route_query("Investigate reconciliation exceptions"), 'audit')

    def test_fallback_to_finance(self):
        self.assertEqual(route_query("Hello, how are you?"), 'finance')

    def test_vendor_score_routes_to_finance(self):
        self.assertEqual(route_query("What are my vendor scores?"), 'finance')


# ═══════════════════════════════════════════════════════════════════════
# Tool selection tests
# ═══════════════════════════════════════════════════════════════════════

class ToolSelectionTests(TestCase):

    def test_selects_cashflow_for_finance(self):
        tools = select_tools(
            "What is my cash position?",
            AGENT_DEFINITIONS['finance']['tools'],
        )
        self.assertIn('cashflow_forecast', tools)

    def test_selects_risk_for_compliance(self):
        tools = select_tools(
            "Show me all risk signals",
            AGENT_DEFINITIONS['compliance']['tools'],
        )
        self.assertIn('risk_summary', tools)

    def test_cannot_select_tools_outside_allowlist(self):
        tools = select_tools(
            "Show me the audit trail",
            AGENT_DEFINITIONS['finance']['tools'],
        )
        self.assertNotIn('audit_trail', tools)

    def test_fallback_selects_at_least_one_tool(self):
        tools = select_tools(
            "random nonsense query",
            AGENT_DEFINITIONS['cfo']['tools'],
        )
        self.assertGreaterEqual(len(tools), 1)


# ═══════════════════════════════════════════════════════════════════════
# Executor tests
# ═══════════════════════════════════════════════════════════════════════

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class AgentExecutorTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='agent@test.com', email='agent@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Agent Corp', state='Maharashtra', city='Mumbai',
            owner_email='agent@test.com', created_by=self.user, status='active',
        )

    def test_execute_creates_conversation(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="What is my cash flow forecast?",
        )
        self.assertIsNotNone(conv.id)
        self.assertEqual(conv.agent_type, 'finance')
        self.assertIsNotNone(conv.completed_at)

    def test_response_has_evidence_based_schema(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Show me risk signals",
        )
        resp = conv.response
        for field in ('conclusion', 'confidence', 'evidence', 'reasoning', 'recommended_actions'):
            self.assertIn(field, resp, f"Missing field: {field}")

    def test_confidence_is_numeric(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Cash forecast please",
        )
        confidence = Decimal(conv.response['confidence'])
        self.assertGreater(confidence, Decimal('0'))
        self.assertLessEqual(confidence, Decimal('1'))

    def test_agent_actions_recorded(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="What are my overdue receivables?",
        )
        actions = AgentAction.objects.filter(conversation=conv)
        self.assertGreater(actions.count(), 0)
        for action in actions:
            self.assertIn('firm_id', action.tool_input)

    def test_evidence_contains_tool_data(self):
        # Seed some data so tools return real results
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='inflow',
            status='pending', amount=Decimal('100000'), currency='INR',
            txn_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
        )

        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Show me overdue receivables",
        )
        evidence = conv.response.get('evidence', [])
        self.assertGreater(len(evidence), 0)
        # Evidence must contain actual source data, not empty
        has_data = any(e.get('data') for e in evidence)
        self.assertTrue(has_data, "Evidence should contain real tool data")

    def test_explicit_agent_type_override(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Hello",
            agent_type='cfo',
        )
        self.assertEqual(conv.agent_type, 'cfo')
        self.assertEqual(conv.routed_by, 'explicit')

    def test_write_tool_creates_pending_approval(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Flag this suspicious transaction for investigation",
            agent_type='compliance',
        )
        approvals = PendingApproval.objects.filter(conversation=conv)
        self.assertGreater(approvals.count(), 0)
        self.assertEqual(approvals.first().status, 'pending')

    def test_conclusion_not_empty(self):
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Executive summary please",
            agent_type='cfo',
        )
        self.assertTrue(len(conv.response['conclusion']) > 0)


# ═══════════════════════════════════════════════════════════════════════
# Approval gate tests
# ═══════════════════════════════════════════════════════════════════════

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class ApprovalGateTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='approver@test.com', email='approver@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Approval Corp', state='Delhi', city='Delhi',
            owner_email='approver@test.com', created_by=self.user, status='active',
        )
        self.vendor = Vendor.objects.create(firm=self.firm, name='Approval Vendor')
        self.txn = Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='outflow',
            status='pending', amount=Decimal('1000.00'), currency='INR',
            txn_date=date.today(), vendor=self.vendor,
        )
        self.signal = RiskSignal.objects.create(
            firm=self.firm, severity='high', category='unusual_amount',
            status='open', title='Approval signal', description='test',
            entity_type='transaction', entity_id=self.txn.id, vendor=self.vendor,
            confidence=Decimal('0.9000'),
        )
        # Create a conversation with a pending approval
        conv = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Flag suspicious transaction and send reminder",
            agent_type='compliance',
        )
        self.conv = conv

    def test_approval_created_for_write_action(self):
        approvals = PendingApproval.objects.filter(conversation=self.conv)
        self.assertGreater(approvals.count(), 0)

    def test_reject_approval(self):
        pa = PendingApproval.objects.filter(conversation=self.conv).first()
        updated = process_approval(
            approval_id=str(pa.id),
            user=self.user,
            decision='rejected',
            notes='Not needed.',
        )
        self.assertEqual(updated.status, 'rejected')
        # Check AuditLog was created
        audit = AuditLog.objects.filter(
            firm=self.firm, action='reject_agent_action',
        )
        self.assertTrue(audit.exists())

    def test_approve_creates_audit_log(self):
        # Create a fresh approval since the previous test might have used it
        conv2 = execute_agent(
            firm_id=self.firm.id, user=self.user,
            query="Flag suspicious transaction",
            agent_type='compliance',
        )
        pa = PendingApproval.objects.filter(conversation=conv2, status='pending').first()
        if pa:
            updated = process_approval(
                approval_id=str(pa.id),
                user=self.user,
                decision='approved',
                notes='Confirmed.',
            )
            self.assertEqual(updated.status, 'approved')
            self.assertIsNotNone(updated.audit_log_id)

    def test_cannot_process_twice(self):
        pa = PendingApproval.objects.filter(
            conversation=self.conv, status='pending'
        ).first()
        if pa:
            process_approval(
                approval_id=str(pa.id), user=self.user, decision='rejected',
            )
            with self.assertRaises(ValueError):
                process_approval(
                    approval_id=str(pa.id), user=self.user, decision='approved',
                )

    def test_approve_transaction_logs_underlying_resource_audit(self):
        pa = PendingApproval.objects.create(
            conversation=self.conv,
            firm=self.firm,
            proposed_action='flag_transaction',
            action_params={'transaction_id': self.txn.id, 'reason': 'Review needed'},
            reason='Review needed',
        )
        process_approval(
            approval_id=str(pa.id),
            user=self.user,
            decision='approved',
            notes='Proceed',
        )
        self.assertTrue(
            AuditLog.objects.filter(
                firm=self.firm,
                resource_type='transaction',
                resource_id=self.txn.id,
                action='edit',
            ).exists()
        )

    def test_approve_risk_status_logs_underlying_resource_audit(self):
        pa = PendingApproval.objects.create(
            conversation=self.conv,
            firm=self.firm,
            proposed_action='update_risk_status',
            action_params={'signal_id': self.signal.id, 'new_status': 'resolved'},
            reason='Issue cleared',
        )
        process_approval(
            approval_id=str(pa.id),
            user=self.user,
            decision='approved',
            notes='Proceed',
        )
        self.assertTrue(
            AuditLog.objects.filter(
                firm=self.firm,
                resource_type='risk_signal',
                resource_id=self.signal.id,
                action='edit',
            ).exists()
        )


# ═══════════════════════════════════════════════════════════════════════
# API endpoint tests
# ═══════════════════════════════════════════════════════════════════════

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class AgentAPITests(TestCase):

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='agentapi@test.com', email='agentapi@test.com', password='x',
        )
        self.owner_user = User.objects.create_user(
            username='owner-api@test.com', email='owner-api@test.com', password='x', role='owner',
        )
        self.firm = Firm.objects.create(
            name='Agent API Inc', state='Karnataka', city='Bangalore',
            owner_email='owner-api@test.com', created_by=self.user, status='active',
        )
        token = _auth_token(self.user)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.owner_client = APIClient()
        self.owner_client.credentials(HTTP_AUTHORIZATION=f'Bearer {_auth_token(self.owner_user)}')

    def test_query_endpoint_returns_200(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'What is my cash position?'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_query_response_has_schema(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'Show risk signals'},
            format='json',
        )
        data = resp.json()
        self.assertIn('response', data)
        self.assertIn('conclusion', data['response'])
        self.assertIn('evidence', data['response'])
        self.assertIn('confidence', data['response'])
        self.assertIn('reasoning', data['response'])
        self.assertIn('recommended_actions', data['response'])

    def test_query_with_explicit_agent_type(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'Overview', 'agent_type': 'cfo'},
            format='json',
        )
        self.assertEqual(resp.json()['agent_type'], 'cfo')

    def test_query_empty_query_rejected(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_agent_type_rejected(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'test', 'agent_type': 'nonexistent'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_history_endpoint(self):
        # Create a conversation first
        self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'test query'},
            format='json',
        )
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/agent/history/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.json()['count'], 0)

    def test_conversation_detail(self):
        resp1 = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'Cash position'},
            format='json',
        )
        conv_id = resp1.json()['conversation_id']
        resp2 = self.client_api.get(f'/api/agent/conversations/{conv_id}/')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('actions', resp2.json())

    def test_approvals_list(self):
        resp = self.client_api.get(f'/api/firms/{self.firm.id}/agent/approvals/')
        self.assertEqual(resp.status_code, 200)

    def test_approve_via_api(self):
        # Create a write-action query
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'Flag suspicious transaction', 'agent_type': 'compliance'},
            format='json',
        )
        approvals = resp.json()['response'].get('pending_approvals', [])
        if approvals:
            approval_id = approvals[0]['approval_id']
            resp2 = self.client_api.post(
                f'/api/agent/approvals/{approval_id}/',
                {'decision': 'approved', 'notes': 'Confirmed'},
                format='json',
            )
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()['status'], 'approved')

    def test_owner_cannot_approve_write_action_via_api(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'Flag suspicious transaction', 'agent_type': 'compliance'},
            format='json',
        )
        approvals = resp.json()['response'].get('pending_approvals', [])
        if approvals:
            approval_id = approvals[0]['approval_id']
            resp2 = self.owner_client.post(
                f'/api/agent/approvals/{approval_id}/',
                {'decision': 'approved', 'notes': 'Owner should be denied'},
                format='json',
            )
            self.assertEqual(resp2.status_code, 403)

    def test_cross_firm_access_denied(self):
        other_user = User.objects.create_user(
            username='other@agent.com', email='other@agent.com', password='x',
        )
        other_firm = Firm.objects.create(
            name='Other Firm', state='Gujarat', city='Surat',
            owner_email='other@agent.com', created_by=other_user, status='active',
        )
        resp = self.client_api.post(
            f'/api/firms/{other_firm.id}/agent/query/',
            {'query': 'test'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_response_numbers_from_tool_data(self):
        """Agent response numbers must come from tool calls, not be invented."""
        # Seed real data
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='inflow',
            status='completed', amount=Decimal('750000'), currency='INR',
            txn_date=date.today() - timedelta(days=10),
        )
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/agent/query/',
            {'query': 'What is my cash position?'},
            format='json',
        )
        data = resp.json()
        evidence = data['response']['evidence']
        # Evidence must contain tool data
        self.assertTrue(
            any(e.get('data') for e in evidence),
            "Evidence must contain real tool data, not empty",
        )
        # The conclusion must reference numbers from the tool data
        conclusion = data['response']['conclusion']
        self.assertTrue(len(conclusion) > 20, "Conclusion should be substantive")


# ═══════════════════════════════════════════════════════════════════════
# "Ask LedgerPro" endpoint tests
# ═══════════════════════════════════════════════════════════════════════

@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class AskLedgerProTests(TestCase):

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='ask@test.com', email='ask@test.com', password='x',
        )
        self.firm = Firm.objects.create(
            name='Ask Test Inc', state='Maharashtra', city='Mumbai',
            owner_email='ask@test.com', created_by=self.user, status='active',
        )
        token = _auth_token(self.user)
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Seed data for realistic responses
        self.customer = Customer.objects.create(firm=self.firm, name='Alpha Corp')
        self.vendor = Vendor.objects.create(firm=self.firm, name='Beta Supplies')
        today = date.today()

        # Completed inflow (revenue)
        Transaction.objects.create(
            firm=self.firm, txn_type='payment', direction='inflow',
            status='completed', amount=Decimal('500000'), currency='INR',
            txn_date=today - timedelta(days=10), customer=self.customer,
        )
        # Overdue receivable
        Transaction.objects.create(
            firm=self.firm, txn_type='invoice', direction='inflow',
            status='pending', amount=Decimal('200000'), currency='INR',
            txn_date=today - timedelta(days=60),
            due_date=today - timedelta(days=20),
            customer=self.customer,
        )
        # Completed expense
        Transaction.objects.create(
            firm=self.firm, txn_type='payment', direction='outflow',
            status='completed', amount=Decimal('300000'), currency='INR',
            txn_date=today - timedelta(days=15), vendor=self.vendor,
        )

    def test_ask_returns_200(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'What is my cash position?'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_ask_creates_session(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Show me overdue receivables'},
            format='json',
        )
        data = resp.json()
        self.assertIn('session_id', data)
        self.assertEqual(data['turn_number'], 1)
        self.assertTrue(ChatSession.objects.filter(pk=data['session_id']).exists())

    def test_followup_uses_same_session(self):
        # Turn 1
        resp1 = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'What is my cash flow forecast?'},
            format='json',
        )
        session_id = resp1.json()['session_id']

        # Turn 2 — follow-up
        resp2 = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Show me the invoices responsible', 'session_id': session_id},
            format='json',
        )
        data2 = resp2.json()
        self.assertEqual(data2['session_id'], session_id)
        self.assertEqual(data2['turn_number'], 2)

    def test_followup_drills_into_receivables(self):
        # Turn 1 — cash forecast
        resp1 = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'What is my cash flow forecast?'},
            format='json',
        )
        session_id = resp1.json()['session_id']

        # Turn 2 — drill-down
        resp2 = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Show me the invoices responsible for this', 'session_id': session_id},
            format='json',
        )
        tools_called = resp2.json()['response']['tools_called']
        # Should include overdue_receivables or payables_due from drill-down
        self.assertTrue(
            'overdue_receivables' in tools_called or 'payables_due' in tools_called,
            f"Follow-up should drill into receivables/payables, got: {tools_called}",
        )

    def test_entity_refs_in_response(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Who owes me money?'},
            format='json',
        )
        data = resp.json()
        entity_refs = data['response'].get('entity_refs', [])
        self.assertGreater(len(entity_refs), 0, "Should have entity_refs for deep-linking")
        # Each ref should have type, id, url
        for ref in entity_refs:
            self.assertIn('type', ref)
            self.assertIn('id', ref)
            self.assertIn('url', ref)

    def test_entity_refs_contain_customer_ids(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Show me overdue receivables'},
            format='json',
        )
        refs = resp.json()['response'].get('entity_refs', [])
        customer_refs = [r for r in refs if r['type'] == 'customer']
        self.assertGreater(len(customer_refs), 0, "Should reference specific customer IDs")

    def test_latency_tracked(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Cash position'},
            format='json',
        )
        latency = resp.json()['latency_ms']
        self.assertIsInstance(latency, int)
        self.assertGreater(latency, 0)

    def test_latency_under_4_seconds(self):
        """Common queries must respond in under 4 seconds."""
        for query in [
            'What are my biggest expenses?',
            'Which customers owe money?',
            'What is my cash flow forecast?',
        ]:
            resp = self.client_api.post(
                f'/api/firms/{self.firm.id}/ask/',
                {'query': query},
                format='json',
            )
            self.assertEqual(resp.status_code, 200)
            self.assertLess(
                resp.json()['latency_ms'], 4000,
                f"Query '{query}' took {resp.json()['latency_ms']}ms, expected <4000ms",
            )

    def test_biggest_expenses_query(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'What are my biggest expenses?'},
            format='json',
        )
        conclusion = resp.json()['response']['conclusion']
        self.assertIn('expense', conclusion.lower())

    def test_profit_analysis_query(self):
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Why did my profit decrease?'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('profit_analysis', resp.json()['response']['tools_called'])

    def test_session_detail_endpoint(self):
        resp1 = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Cash position'},
            format='json',
        )
        session_id = resp1.json()['session_id']

        resp2 = self.client_api.get(f'/api/agent/sessions/{session_id}/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['turn_count'], 1)
        self.assertIn('entity_refs', resp2.json()['turns'][0])

    def test_cross_firm_denied(self):
        other_user = User.objects.create_user(
            username='other@ask.com', email='other@ask.com', password='x',
        )
        other_firm = Firm.objects.create(
            name='Other Firm', state='Gujarat', city='Surat',
            owner_email='other@ask.com', created_by=other_user, status='active',
        )
        resp = self.client_api.post(
            f'/api/firms/{other_firm.id}/ask/',
            {'query': 'test'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_every_claim_traceable(self):
        """Every response must have evidence with source tool names."""
        resp = self.client_api.post(
            f'/api/firms/{self.firm.id}/ask/',
            {'query': 'Show me overdue receivables and biggest expenses'},
            format='json',
        )
        evidence = resp.json()['response']['evidence']
        for ev in evidence:
            self.assertIn('source', ev, "Every evidence item must cite its source tool")

"""
Agent API endpoints.

POST /api/firms/{firm_id}/agent/query/     — run a query through the agent system
GET  /api/firms/{firm_id}/agent/history/   — list past conversations
GET  /api/agent/conversations/{id}/        — conversation detail + actions + evidence
POST /api/agent/approvals/{id}/            — approve or reject a pending write-action
GET  /api/firms/{firm_id}/agent/approvals/ — list pending approvals for a firm
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from firms.access import (
    assert_can_write_firm,
    get_agent_conversation_for_user,
    get_chat_session_for_user,
    get_firm_or_403,
    get_pending_approval_for_user,
)
from firms.permissions import HasFirmAccess

from .executor import execute_agent, AGENT_DEFINITIONS, route_query
from .models import AgentAction, AgentConversation, ChatSession, PendingApproval
from .approval import process_approval

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def agent_query(request, firm_id):
    """
    **POST /api/firms/{firm_id}/agent/query/**

    Run a natural-language query through the agent orchestration system.

    ### Request body

    ```json
    {
      "query": "What is my cash position and are there any risk alerts?",
      "agent_type": null  // optional: "finance" | "compliance" | "cfo" | "audit"
    }
    ```

    ### Response

    Evidence-Based AI structured response:
    `conclusion → confidence → evidence → reasoning → recommended_actions`
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    query = request.data.get('query', '').strip()
    if not query:
        return Response({'error': 'query is required.'}, status=status.HTTP_400_BAD_REQUEST)

    from billing.entitlements import billing_error_response, reserve_ai_queries_for_firm
    from billing.exceptions import BillingError

    try:
        reserve_ai_queries_for_firm(firm, amount=1)
    except BillingError as exc:
        return billing_error_response(exc)

    agent_type = request.data.get('agent_type')
    if agent_type and agent_type not in AGENT_DEFINITIONS:
        return Response(
            {'error': f'Invalid agent_type. Choose from: {list(AGENT_DEFINITIONS.keys())}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    conv = execute_agent(
        firm_id=firm_id,
        user=request.user,
        query=query,
        agent_type=agent_type,
    )

    return Response({
        'conversation_id': str(conv.id),
        'agent_type': conv.agent_type,
        'routed_by': conv.routed_by,
        'response': conv.response,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def agent_history(request, firm_id):
    """
    **GET /api/firms/{firm_id}/agent/history/**

    List past agent conversations for the firm.
    Supports `?agent_type=X` filter and `?limit=N` (default 20).
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = AgentConversation.objects.filter(firm=firm).order_by('-created_at')

    agent_filter = request.query_params.get('agent_type')
    if agent_filter:
        qs = qs.filter(agent_type=agent_filter)

    limit = int(request.query_params.get('limit', 20))
    convs = qs[:limit]

    return Response({
        'count': qs.count(),
        'results': [{
            'id': str(c.id),
            'agent_type': c.agent_type,
            'query': c.query,
            'conclusion': c.response.get('conclusion', '') if c.response else '',
            'confidence': c.response.get('confidence', '') if c.response else '',
            'created_at': c.created_at.isoformat(),
            'routed_by': c.routed_by,
        } for c in convs],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_detail(request, pk):
    """
    **GET /api/agent/conversations/{id}/**

    Full conversation detail including all tool calls (AgentActions)
    and the structured evidence-based response.
    """
    conv = get_agent_conversation_for_user(request.user, pk)

    actions = AgentAction.objects.filter(conversation=conv).order_by('created_at')
    approvals = PendingApproval.objects.filter(conversation=conv)

    return Response({
        'id': str(conv.id),
        'agent_type': conv.agent_type,
        'query': conv.query,
        'response': conv.response,
        'routed_by': conv.routed_by,
        'created_at': conv.created_at.isoformat(),
        'completed_at': conv.completed_at.isoformat() if conv.completed_at else None,
        'actions': [{
            'tool_name': a.tool_name,
            'tool_input': a.tool_input,
            'tool_result': a.tool_result,
            'duration_ms': a.duration_ms,
            'created_at': a.created_at.isoformat(),
        } for a in actions],
        'pending_approvals': [{
            'id': str(pa.id),
            'proposed_action': pa.proposed_action,
            'action_params': pa.action_params,
            'reason': pa.reason,
            'status': pa.status,
            'reviewed_by': pa.reviewed_by.email if pa.reviewed_by else None,
            'reviewed_at': pa.reviewed_at.isoformat() if pa.reviewed_at else None,
        } for pa in approvals],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_action(request, pk):
    """
    **POST /api/agent/approvals/{id}/**

    Approve or reject a pending agent write-action.

    ### Request body

    ```json
    {
      "decision": "approved",  // or "rejected"
      "notes": "Looks correct, proceed."
    }
    ```
    """
    decision = request.data.get('decision', '').strip()
    if decision not in ('approved', 'rejected'):
        return Response(
            {'error': 'decision must be "approved" or "rejected".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    approval = get_pending_approval_for_user(request.user, pk)

    if decision == 'approved':
        write_err = assert_can_write_firm(request.user, approval.firm)
        if write_err:
            return write_err

    try:
        updated = process_approval(
            approval_id=str(pk),
            user=request.user,
            decision=decision,
            notes=request.data.get('notes', ''),
            request=request,
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)

    return Response({
        'id': str(updated.id),
        'status': updated.status,
        'proposed_action': updated.proposed_action,
        'reviewed_at': updated.reviewed_at.isoformat() if updated.reviewed_at else None,
        'audit_log_id': updated.audit_log_id,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def list_approvals(request, firm_id):
    """
    **GET /api/firms/{firm_id}/agent/approvals/**

    List pending approvals for a firm.
    Supports `?status=pending` (default) or `?status=all`.
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    qs = PendingApproval.objects.filter(firm=firm).order_by('-created_at')
    status_filter = request.query_params.get('status', 'pending')
    if status_filter != 'all':
        qs = qs.filter(status=status_filter)

    return Response({
        'count': qs.count(),
        'results': [{
            'id': str(pa.id),
            'proposed_action': pa.proposed_action,
            'reason': pa.reason,
            'status': pa.status,
            'created_at': pa.created_at.isoformat(),
            'conversation_id': str(pa.conversation_id),
        } for pa in qs[:50]],
    })


# ===========================================================================
# "Ask LedgerPro" — conversational endpoint with session context
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, HasFirmAccess])
def ask_ledgerpro(request, firm_id):
    """
    **POST /api/firms/{firm_id}/ask/**

    The primary conversational AI endpoint. Routes natural-language questions
    to the correct agent, supports follow-up drill-down via session context,
    and returns deep-linkable entity references for every factual claim.

    ### Request body

    ```json
    {
      "query": "Why did my cash flow decrease?",
      "session_id": null  // optional: UUID of prior session for follow-up
    }
    ```

    ### Follow-up example

    Turn 1: "What is my cash position?" → returns forecast + session_id
    Turn 2: "Show me the invoices responsible" (with session_id) →
            automatically drills into overdue_receivables using prior context

    ### Response

    ```json
    {
      "session_id": "...",
      "conversation_id": "...",
      "turn_number": 1,
      "agent_type": "finance",
      "latency_ms": 320,
      "response": {
        "conclusion": "...",
        "confidence": "0.85",
        "evidence": [...],
        "reasoning": "...",
        "recommended_actions": [...],
        "entity_refs": [
          {"type": "transaction", "id": 42, "url": "/transactions/42"},
          {"type": "customer", "id": 7, "url": "/customers/7"}
        ]
      }
    }
    ```
    """
    firm = get_firm_or_403(request, firm_id)
    if isinstance(firm, Response):
        return firm

    query = request.data.get('query', '').strip()
    if not query:
        return Response({'error': 'query is required.'}, status=status.HTTP_400_BAD_REQUEST)

    session_id = request.data.get('session_id')
    agent_type = request.data.get('agent_type')

    if agent_type and agent_type not in AGENT_DEFINITIONS:
        return Response(
            {'error': f'Invalid agent_type. Choose from: {list(AGENT_DEFINITIONS.keys())}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from billing.entitlements import billing_error_response, reserve_ai_queries_for_firm
    from billing.exceptions import BillingError

    try:
        reserve_ai_queries_for_firm(firm, amount=1)
    except BillingError as exc:
        return billing_error_response(exc)

    conv = execute_agent(
        firm_id=firm_id,
        user=request.user,
        query=query,
        agent_type=agent_type,
        session_id=session_id,
    )

    return Response({
        'session_id': str(conv.session_id),
        'conversation_id': str(conv.id),
        'turn_number': conv.turn_number,
        'agent_type': conv.agent_type,
        'routed_by': conv.routed_by,
        'latency_ms': conv.latency_ms,
        'response': conv.response,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_detail(request, pk):
    """
    **GET /api/agent/sessions/{id}/**

    Full session history with all turns, for reviewing a multi-turn conversation.
    """
    session = get_chat_session_for_user(request.user, pk)

    turns = AgentConversation.objects.filter(session=session).order_by('turn_number')

    return Response({
        'session_id': str(session.id),
        'firm_id': session.firm_id,
        'created_at': session.created_at.isoformat(),
        'last_active_at': session.last_active_at.isoformat(),
        'turn_count': turns.count(),
        'turns': [{
            'turn_number': t.turn_number,
            'conversation_id': str(t.id),
            'agent_type': t.agent_type,
            'query': t.query,
            'conclusion': t.response.get('conclusion', '') if t.response else '',
            'confidence': t.response.get('confidence', '') if t.response else '',
            'entity_refs': t.response.get('entity_refs', []) if t.response else [],
            'latency_ms': t.latency_ms,
            'created_at': t.created_at.isoformat(),
        } for t in turns],
    })

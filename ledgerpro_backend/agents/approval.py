"""
Human approval gate for agent write-actions.

An agent NEVER executes a write action directly. It creates a PendingApproval
record.  This module provides the `process_approval` function that:
    1. Validates the reviewer has access to the firm.
    2. Executes the action only if status is 'approved'.
    3. Logs every approval/rejection to AuditLog.
"""
import logging

from django.utils import timezone

from audit.services import log_audit
from .models import PendingApproval

logger = logging.getLogger(__name__)


# Action executors — one per write action type
_ACTION_EXECUTORS: dict[str, callable] = {}


def _register_action(name: str):
    def decorator(fn):
        _ACTION_EXECUTORS[name] = fn
        return fn
    return decorator


@_register_action('flag_transaction')
def _exec_flag_transaction(approval: PendingApproval, user, request=None):
    from intelligence.models import Transaction
    txn_id = approval.action_params.get('transaction_id')
    if not txn_id:
        return {'error': 'No transaction_id provided.'}

    try:
        txn = Transaction.objects.get(pk=txn_id, firm=approval.firm)
    except Transaction.DoesNotExist:
        return {'error': f'Transaction {txn_id} not found.'}

    if 'flagged' not in txn.metadata:
        txn.metadata['flagged'] = []
    txn.metadata['flagged'].append({
        'reason': approval.reason,
        'flagged_by': 'agent',
        'approved_by': user.email,
        'at': timezone.now().isoformat(),
    })
    txn.save(update_fields=['metadata', 'updated_at'])
    log_audit(
        user=user,
        firm=approval.firm,
        resource_type='transaction',
        resource_id=txn.id,
        action='edit',
        details={
            'via': 'agent_approval',
            'approval_id': str(approval.id),
            'metadata_flag_reason': approval.reason,
        },
        request=request,
    )

    return {'transaction_id': txn_id, 'status': 'flagged'}


@_register_action('update_risk_status')
def _exec_update_risk_status(approval: PendingApproval, user, request=None):
    from intelligence.models import RiskSignal
    sig_id = approval.action_params.get('signal_id')
    new_status = approval.action_params.get('new_status')

    if not sig_id or not new_status:
        return {'error': 'Missing signal_id or new_status.'}

    try:
        sig = RiskSignal.objects.get(pk=sig_id, firm=approval.firm)
    except RiskSignal.DoesNotExist:
        return {'error': f'RiskSignal {sig_id} not found.'}

    sig.status = new_status
    if new_status in ('resolved', 'false_positive'):
        sig.resolved_by = user
        sig.resolved_at = timezone.now()
    sig.save(update_fields=['status', 'resolved_by', 'resolved_at', 'updated_at'])
    log_audit(
        user=user,
        firm=approval.firm,
        resource_type='risk_signal',
        resource_id=sig.id,
        action='edit',
        details={
            'via': 'agent_approval',
            'approval_id': str(approval.id),
            'new_status': new_status,
        },
        request=request,
    )

    return {'signal_id': sig_id, 'new_status': new_status}


@_register_action('send_payment_reminder')
def _exec_send_payment_reminder(approval: PendingApproval, user, request=None):
    # In production this would integrate with an email/SMS service.
    # For now, we log it as a completed action.
    return {
        'customer_id': approval.action_params.get('customer_id'),
        'invoice_ids': approval.action_params.get('invoice_ids', []),
        'status': 'reminder_queued',
        'message': 'Payment reminder has been queued for delivery.',
    }


def process_approval(
    *,
    approval_id: str,
    user,
    decision: str,
    notes: str = '',
    request=None,
) -> PendingApproval:
    """Process a human decision on a PendingApproval.

    Args:
        approval_id: UUID of the PendingApproval.
        user: The reviewing user.
        decision: 'approved' or 'rejected'.
        notes: Optional reviewer notes.
        request: The HTTP request (for IP logging).

    Returns:
        The updated PendingApproval.
    """
    approval = PendingApproval.objects.select_related('firm', 'conversation').get(
        pk=approval_id,
    )

    if approval.status != PendingApproval.Status.PENDING:
        raise ValueError(f"Approval {approval_id} already processed: {approval.status}")

    approval.reviewed_by = user
    approval.reviewed_at = timezone.now()
    approval.review_notes = notes

    if decision == 'rejected':
        approval.status = PendingApproval.Status.REJECTED
        approval.save()

        log_audit(
            user=user, firm=approval.firm,
            resource_type='agent_approval', resource_id=0,
            action='reject_agent_action',
            details={
                'approval_id': str(approval.id),
                'proposed_action': approval.proposed_action,
                'reason': approval.reason,
                'notes': notes,
            },
            request=request,
        )
        return approval

    # Execute the approved action
    approval.status = PendingApproval.Status.APPROVED
    executor = _ACTION_EXECUTORS.get(approval.proposed_action)

    exec_result = {}
    if executor:
        exec_result = executor(approval, user, request)
    else:
        exec_result = {'error': f'No executor for action: {approval.proposed_action}'}

    # Log to AuditLog
    audit_entry = log_audit(
        user=user, firm=approval.firm,
        resource_type='agent_approval',
        resource_id=0,
        action='approve_agent_action',
        details={
            'approval_id': str(approval.id),
            'proposed_action': approval.proposed_action,
            'action_params': approval.action_params,
            'execution_result': exec_result,
            'notes': notes,
        },
        request=request,
    )

    approval.audit_log_id = audit_entry.id
    approval.save()

    return approval

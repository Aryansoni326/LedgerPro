"""
Agent orchestration models.

AgentConversation — tracks a multi-turn session with a user.
AgentAction      — records every tool call + result for audit.
PendingApproval  — write-actions that require human sign-off.
"""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatSession(models.Model):
    """A multi-turn conversational session.

    Groups sequential AgentConversation turns so follow-up questions
    ("show me the invoices responsible") can resolve references from
    prior turns without re-asking.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey('firms.Firm', on_delete=models.CASCADE, related_name='chat_sessions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_active_at']
        indexes = [
            models.Index(fields=['firm', 'user', '-last_active_at']),
        ]

    def __str__(self):
        return f"ChatSession {self.id} ({self.firm_id})"


class AgentConversation(models.Model):
    """A single agent turn scoped to a firm + user."""

    class AgentType(models.TextChoices):
        FINANCE = "finance", "Finance Agent"
        COMPLIANCE = "compliance", "Compliance Agent"
        CFO = "cfo", "CFO Agent"
        AUDIT = "audit", "Audit Agent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey('firms.Firm', on_delete=models.CASCADE, related_name='agent_conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, null=True, blank=True,
        related_name='turns',
        help_text="Links this turn to a multi-turn session for follow-up context.",
    )
    turn_number = models.PositiveIntegerField(default=1)
    agent_type = models.CharField(max_length=20, choices=AgentType.choices)
    query = models.TextField(help_text="The user's original question.")
    response = models.JSONField(default=dict, blank=True,
                                help_text="Evidence-Based AI structured response.")
    routed_by = models.CharField(max_length=30, default='auto',
                                 help_text="How the agent was selected: auto | explicit.")
    latency_ms = models.PositiveIntegerField(default=0, help_text="Total response time in ms.")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'agent_type', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.agent_type} conv {self.id} ({self.firm_id})"


class AgentAction(models.Model):
    """Immutable record of a single tool invocation by an agent.

    Every number in the agent's final response must be traceable back to
    an AgentAction.tool_result — this is the evidence chain.
    """

    conversation = models.ForeignKey(
        AgentConversation, on_delete=models.CASCADE, related_name='actions',
    )
    tool_name = models.CharField(max_length=100)
    tool_input = models.JSONField(default=dict)
    tool_result = models.JSONField(default=dict)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.tool_name} @ {self.conversation_id}"


class PendingApproval(models.Model):
    """Write-actions that need explicit human sign-off.

    An agent NEVER executes a write action directly. Instead it creates
    a PendingApproval with the proposed action + params. A human then
    approves/rejects, and the system executes only after approval — with
    a full AuditLog entry.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AgentConversation, on_delete=models.CASCADE, related_name='pending_approvals',
    )
    firm = models.ForeignKey('firms.Firm', on_delete=models.CASCADE)
    proposed_action = models.CharField(max_length=100,
                                       help_text="e.g. 'flag_transaction', 'send_reminder', 'update_risk_status'")
    action_params = models.JSONField(default=dict)
    reason = models.TextField(help_text="Agent's justification for the proposed action.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default='')
    audit_log_id = models.PositiveIntegerField(null=True, blank=True,
                                                help_text="AuditLog.id created after approval execution.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'status', '-created_at']),
        ]

    def __str__(self):
        return f"Approval {self.id} [{self.proposed_action}] — {self.status}"

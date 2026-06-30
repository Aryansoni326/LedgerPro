from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Immutable audit trail for financial document operations."""

    ACTION_UPLOAD = 'upload'
    ACTION_EDIT = 'edit'
    ACTION_DELETE = 'delete'
    ACTION_VERIFY = 'verify'
    ACTION_EXPORT = 'export'
    ACTION_RETRY = 'retry_extraction'

    ACTION_CHOICES = [
        (ACTION_UPLOAD, 'Upload'),
        (ACTION_EDIT, 'Edit'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_VERIFY, 'Verify'),
        (ACTION_EXPORT, 'Export'),
        (ACTION_RETRY, 'Retry Extraction'),
    ]

    RESOURCE_BILL = 'bill'
    RESOURCE_IMPORT_EXPORT = 'import_export_record'
    RESOURCE_EWAY_BILL = 'eway_bill_record'

    RESOURCE_CHOICES = [
        (RESOURCE_BILL, 'Bill'),
        (RESOURCE_IMPORT_EXPORT, 'Import-Export Record'),
        (RESOURCE_EWAY_BILL, 'E-Way Bill Record'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
    )
    firm = models.ForeignKey(
        'firms.Firm',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
    )
    resource_type = models.CharField(max_length=40, choices=RESOURCE_CHOICES)
    resource_id = models.PositiveIntegerField()
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['firm', 'resource_type', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]

    def __str__(self):
        actor = self.user.email if self.user else 'system'
        return f"{self.timestamp:%Y-%m-%d %H:%M} {actor} {self.action} {self.resource_type}:{self.resource_id}"

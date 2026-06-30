from django.conf import settings
from django.db import models

from firms.models import Firm


class Bill(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('needs_review', 'Needs Review'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('extraction_failed', 'Extraction Failed') # dead-letter state
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='bills')
    file_name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=1000)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='processing')
    file_size = models.IntegerField() # In bytes
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_bills'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    raw_data = models.JSONField(blank=True, null=True)
    extraction_raw_json = models.TextField(blank=True, null=True)
    validation_warnings = models.JSONField(default=list, blank=True)
    extraction_failed = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Bill {self.file_name} ({self.status}) for {self.firm.name}"


class ExcelExportBatch(models.Model):
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='exports')
    file_name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=1000)
    exported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='excel_exports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    bill_ids = models.JSONField(default=list)

    def __str__(self):
        return f"Export Batch {self.file_name} for {self.firm.name}"


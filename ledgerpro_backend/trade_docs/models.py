from django.conf import settings
from django.db import models

from firms.models import Firm


class ImportExportRecord(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('needs_review', 'Needs Review'),
        ('verified', 'Verified'),
        ('extraction_failed', 'Extraction Failed'),
    ]

    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='trade_docs')
    file_name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=1000)
    file_size = models.IntegerField(default=0)  # bytes
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='processing')

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_trade_docs'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Extracted fields (stored as raw JSON for flexibility)
    raw_data = models.JSONField(blank=True, null=True)
    extraction_raw_json = models.TextField(blank=True, null=True)
    validation_warnings = models.JSONField(default=list, blank=True)
    extraction_failed = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    # Canonical schema fields — mirrored from raw_data for fast lookups
    be_number = models.CharField(max_length=100, blank=True, null=True)
    be_date = models.DateField(blank=True, null=True)
    port_code = models.CharField(max_length=20, blank=True, null=True)
    container_id = models.CharField(max_length=1000, blank=True, null=True)
    gross_weight = models.DecimalField(max_digits=14, decimal_places=3, blank=True, null=True)
    net_weight = models.DecimalField(max_digits=14, decimal_places=3, blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)
    assessable_value = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    shipper_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Trade Doc {self.file_name} ({self.status}) for {self.firm.name}"

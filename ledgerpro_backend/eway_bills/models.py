from django.conf import settings
from django.db import models

from firms.models import Firm


class EwayBillRecord(models.Model):
  """E-way bill / transit permit document stored per firm."""

  STATUS_CHOICES = [
      ('processing', 'Processing'),
      ('needs_review', 'Needs Review'),
      ('verified', 'Verified'),
      ('extraction_failed', 'Extraction Failed'),
  ]

  firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='eway_bills')
  file_name = models.CharField(max_length=255)
  file_url = models.CharField(max_length=1000)
  file_size = models.IntegerField(default=0)
  status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='processing')

  uploaded_by = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.CASCADE,
      related_name='uploaded_eway_bills',
  )
  uploaded_at = models.DateTimeField(auto_now_add=True)
  is_deleted = models.BooleanField(default=False)

  # Optional extracted / manual fields (populated in future phases)
  eway_bill_number = models.CharField(max_length=100, blank=True, null=True)
  be_number = models.CharField(max_length=100, blank=True, null=True)
  vehicle_number = models.CharField(max_length=50, blank=True, null=True)
  raw_data = models.JSONField(blank=True, null=True)
  extraction_failed = models.BooleanField(default=False)
  validation_warnings = models.JSONField(default=list, blank=True)
  extraction_raw_json = models.TextField(blank=True, null=True)

  class Meta:
      ordering = ['-uploaded_at']

  def __str__(self):
      return f"E-Way Bill {self.file_name} for {self.firm.name}"

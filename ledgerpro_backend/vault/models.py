from django.db import models
from django.utils import timezone

from invoices.models import Bill, ExcelExportBatch
from trade_docs.models import ImportExportRecord

MODULE_CHOICES = [
    ('invoices', 'Invoices'),
    ('exports', 'Excel Exports'),
    ('import_export', 'Import-Export Customs'),
    ('eway_bills', 'E-Way Bills'),
]

class CloudVaultEntry(models.Model):
    firm = models.ForeignKey('firms.Firm', on_delete=models.CASCADE, related_name='vault_entries')
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name='vault_entries')
    excel_export = models.ForeignKey(ExcelExportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='vault_entries')
    trade_doc = models.ForeignKey(ImportExportRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='vault_entries')
    eway_bill = models.ForeignKey('eway_bills.EwayBillRecord', on_delete=models.SET_NULL, null=True, blank=True, related_name='vault_entries')
    file_name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=1000)
    module = models.CharField(max_length=50, choices=MODULE_CHOICES, default='invoices')
    is_finalized = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vault Entry: {self.file_name} ({self.module}) - Finalized: {self.is_finalized}"

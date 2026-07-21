from django.contrib import admin

from .models import EwayBillRecord


@admin.register(EwayBillRecord)
class EwayBillRecordAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'firm', 'status', 'file_size', 'uploaded_by', 'uploaded_at', 'is_deleted', 'eway_bill_number')
    list_filter = ('status', 'is_deleted')
    search_fields = ('file_name', 'firm__name', 'uploaded_by__email', 'eway_bill_number')

from django.contrib import admin

from .models import Bill, ExcelExportBatch


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'firm', 'status', 'file_size', 'uploaded_by', 'uploaded_at', 'is_deleted')
    list_filter = ('status', 'is_deleted')
    search_fields = ('file_name', 'firm__name', 'uploaded_by__email')

@admin.register(ExcelExportBatch)
class ExcelExportBatchAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'firm', 'exported_by', 'created_at')
    search_fields = ('file_name', 'firm__name', 'exported_by__email')

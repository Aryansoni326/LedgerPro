from django.contrib import admin

from .models import ImportExportRecord


@admin.register(ImportExportRecord)
class ImportExportRecordAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'firm', 'status', 'file_size', 'uploaded_by', 'uploaded_at', 'is_deleted', 'be_number')
    list_filter = ('status', 'is_deleted')
    search_fields = ('file_name', 'firm__name', 'uploaded_by__email', 'be_number')

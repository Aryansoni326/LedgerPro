from django.contrib import admin
from .models import CloudVaultEntry

@admin.register(CloudVaultEntry)
class CloudVaultEntryAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'firm', 'module', 'is_finalized', 'is_deleted', 'uploaded_at')
    list_filter = ('module', 'is_finalized', 'is_deleted')
    search_fields = ('file_name', 'firm__name')

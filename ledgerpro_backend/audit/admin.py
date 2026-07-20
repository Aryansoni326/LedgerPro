from django.contrib import admin
from .models import AuditLog, FirmAccessLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'firm', 'resource_type', 'resource_id', 'action', 'ip_address')
    list_filter = ('resource_type', 'action')
    search_fields = ('user__email', 'firm__name', 'details')


@admin.register(FirmAccessLog)
class FirmAccessLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'firm', 'event_type', 'ip_address')
    list_filter = ('event_type',)
    search_fields = ('user__email', 'firm__name')

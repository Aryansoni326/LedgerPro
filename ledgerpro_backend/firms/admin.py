from django.contrib import admin
from .models import Firm

@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display = ('name', 'gstin', 'city', 'state', 'owner_email', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'state')
    search_fields = ('name', 'gstin', 'owner_email', 'created_by__email')

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, OTPVerification, OTPResendTracker, OTPRateLimitEvent

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'role', 'is_staff', 'is_superuser', 'is_profile_complete')
    fieldsets = UserAdmin.fieldsets + (
        ('LedgerPro Profile', {'fields': ('role', 'phone_number', 'pan_number', 'location', 'organization', 'is_profile_complete', 'google_sub', 'avatar_url')}),
    )

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('email', 'user', 'purpose', 'is_verified', 'is_locked', 'created_at', 'expires_at')
    list_filter = ('purpose', 'is_verified', 'is_locked')
    search_fields = ('email', 'user__email')

@admin.register(OTPResendTracker)
class OTPResendTrackerAdmin(admin.ModelAdmin):
    list_display = ('email', 'timestamp')
    search_fields = ('email',)

@admin.register(OTPRateLimitEvent)
class OTPRateLimitEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'email', 'ip_address', 'timestamp')
    list_filter = ('event_type',)
    search_fields = ('email', 'ip_address')

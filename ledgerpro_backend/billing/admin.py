from django.contrib import admin

from billing.models import Subscription, UsagePeriod


class UsagePeriodInline(admin.TabularInline):
    model = UsagePeriod
    extra = 0
    readonly_fields = ("period_start", "period_end", "documents_count", "ai_queries_count", "updated_at")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "tier", "status", "current_period_start", "current_period_end")
    list_filter = ("tier", "status")
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [UsagePeriodInline]
    # Enterprise custom_config is edited as JSON — no schema migration per customer.


@admin.register(UsagePeriod)
class UsagePeriodAdmin(admin.ModelAdmin):
    list_display = (
        "id", "subscription", "period_start", "documents_count", "ai_queries_count", "updated_at",
    )
    list_filter = ("period_start",)

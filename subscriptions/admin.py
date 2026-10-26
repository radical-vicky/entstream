from django.contrib import admin

from .models import SubscriptionPlan, UserSubscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    list_editable = ("price", "duration_days", "is_active")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "started_at",
        "expires_at",
        "payment_reference",
    )
    list_filter = ("status", "plan")
    search_fields = (
        "user__username",
        "user__email",
        "payment_reference",
    )
    readonly_fields = ("created_at", "updated_at")
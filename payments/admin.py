
from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "user",
        "purpose",
        "amount",
        "currency",
        "status",
        "provider",
        "created_at",
    )
    list_filter = ("status", "purpose", "provider", "currency", "created_at")
    search_fields = (
        "reference",
        "provider_reference",
        "user__username",
        "user__email",
    )
    readonly_fields = (
        "reference",
        "provider_reference",
        "verified_at",
        "provider_payload",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

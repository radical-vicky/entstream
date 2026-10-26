from django.contrib import admin

from .models import (
    CreatorBalance,
    EarningTransaction,
    WithdrawalRequest,
)


@admin.register(CreatorBalance)
class CreatorBalanceAdmin(admin.ModelAdmin):
    list_display = (
        "creator",
        "available_balance",
        "pending_balance",
        "total_earned",
        "total_paid_out",
        "updated_at",
    )
    search_fields = ("creator__username", "creator__email")
    readonly_fields = ("updated_at",)


@admin.register(EarningTransaction)
class EarningTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "creator",
        "transaction_type",
        "amount",
        "status",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "transaction_type", "created_at")
    search_fields = (
        "reference",
        "external_reference",
        "creator__username",
    )
    readonly_fields = (
        "reference",
        "created_at",
        "completed_at",
    )


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "creator",
        "amount",
        "payout_method",
        "status",
        "created_at",
    )
    list_filter = ("status", "payout_method", "created_at")
    search_fields = (
        "reference",
        "creator__username",
        "creator__email",
    )
    readonly_fields = (
        "reference",
        "created_at",
        "updated_at",
        "paid_at",
    )
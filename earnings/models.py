
from decimal import Decimal
import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CreatorBalance(models.Model):
    creator = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streamsphere_balance",
    )
    available_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    pending_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_paid_out = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Balance for {self.creator}"


class EarningTransaction(models.Model):
    class Type(models.TextChoices):
        VIDEO_SALE = "video_sale", "Video sale"
        SUBSCRIPTION = "subscription", "Subscription"
        TIP = "tip", "Tip"
        AD_REVENUE = "ad_revenue", "Ad revenue"
        ADJUSTMENT = "adjustment", "Adjustment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="earning_transactions",
    )
    transaction_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(
        max_length=100,
        unique=True,
        default="",
        blank=True,
    )
    description = models.CharField(max_length=255, blank=True)
    external_reference = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["creator", "status", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=Decimal("0.00")),
                name="earning_transaction_amount_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"ERN-{secrets.token_hex(12).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} — {self.amount} ({self.status})"


class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="withdrawal_requests",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payout_method = models.CharField(max_length=40, default="mpesa")
    payout_account = models.CharField(max_length=150)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reference = models.CharField(
        max_length=100,
        unique=True,
        default="",
        blank=True,
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="withdrawal_request_amount_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"WDR-{secrets.token_hex(12).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} — {self.creator} — {self.amount}"

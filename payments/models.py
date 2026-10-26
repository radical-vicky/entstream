
import secrets

from django.conf import settings
from django.db import models


def generate_payment_reference():
    return secrets.token_urlsafe(24)


class PaymentTransaction(models.Model):
    class Purpose(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        VIDEO_PURCHASE = "video_purchase", "Video purchase"
        TIP = "tip", "Creator tip"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    reference = models.CharField(
        max_length=80,
        unique=True,
        default=generate_payment_reference,
    )
    provider = models.CharField(max_length=40, default="manual")
    provider_reference = models.CharField(
        max_length=160,
        blank=True,
        db_index=True,
    )
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    description = models.CharField(max_length=255, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["purpose", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_transaction_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.amount} {self.currency}"



    video = models.ForeignKey(
    "videos.Video",
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="payment_transactions",
)

    provider_receipt = models.CharField(
    max_length=40,
    blank=True,
    null=True,
    unique=True,
    help_text="Verified provider receipt, such as an M-Pesa receipt number.",
)

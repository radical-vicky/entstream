
from django.conf import settings
from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price", "name"]

    def __str__(self):
        return f"{self.name} — {self.price}"


class UserSubscription(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streamsphere_subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Populate only with a verified transaction reference from your payment system.
    payment_reference = models.CharField(
        max_length=150,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    @property
    def is_current(self):
        return (
            self.status == self.Status.ACTIVE
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )

    def activate(self, payment_reference=""):
        now = timezone.now()

        # Extend an unexpired subscription instead of losing remaining time.
        base_time = now
        if self.is_current and self.expires_at:
            base_time = self.expires_at

        self.status = self.Status.ACTIVE
        self.started_at = self.started_at or now
        self.expires_at = base_time + timezone.timedelta(
            days=self.plan.duration_days
        )
        self.cancelled_at = None

        if payment_reference:
            self.payment_reference = payment_reference

        self.save(
            update_fields=[
                "status",
                "started_at",
                "expires_at",
                "cancelled_at",
                "payment_reference",
                "updated_at",
            ]
        )

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(
            update_fields=["status", "cancelled_at", "updated_at"]
        )

    def __str__(self):
        return f"{self.user} — {self.plan.name} ({self.status})"

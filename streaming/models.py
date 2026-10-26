
import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


def generate_stream_key():
    return secrets.token_urlsafe(32)


class LiveStream(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="live_streams",
    )
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=80, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Keep the stream key private. Never render it on public pages.
    stream_key = models.CharField(
        max_length=100,
        unique=True,
        default=generate_stream_key,
        editable=False,
    )
    ingest_url = models.URLField(blank=True)
    playback_url = models.URLField(blank=True)

    thumbnail_url = models.URLField(blank=True)
    is_public = models.BooleanField(default=True, db_index=True)
    viewer_count = models.PositiveIntegerField(default=0)
    peak_viewers = models.PositiveIntegerField(default=0)
    total_views = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-status", "scheduled_at", "-created_at")
        indexes = [
            models.Index(fields=["status", "is_public"]),
            models.Index(fields=["creator", "status"]),
            models.Index(fields=["scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.creator}"

    def get_absolute_url(self):
        return reverse("streaming:detail", kwargs={"pk": self.pk})

    @property
    def is_live(self):
        return self.status == self.Status.LIVE

    @property
    def can_start(self):
        return self.status == self.Status.SCHEDULED

    def start(self):
        if self.status != self.Status.SCHEDULED:
            return False
        self.status = self.Status.LIVE
        self.started_at = timezone.now()
        self.ended_at = None
        self.save(update_fields=["status", "started_at", "ended_at", "updated_at"])
        return True

    def end(self):
        if self.status != self.Status.LIVE:
            return False
        self.status = self.Status.ENDED
        self.ended_at = timezone.now()
        self.viewer_count = 0
        self.save(update_fields=[
            "status", "ended_at", "viewer_count", "updated_at"
        ])
        return True

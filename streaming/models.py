import re
import secrets
import unicodedata
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def generate_room_key():
    """
    Generate a unique 32-character LiveKit room key.
    This function must remain available because Django migrations
    reference it directly.
    """
    return secrets.token_hex(16)


def generate_stream_key():
    """
    Generate a secure stream key for OBS/RTMP broadcasting.
    """
    return secrets.token_urlsafe(32)


def sanitize_filename(filename):
    """
    Sanitize a filename so it is safe for Cloudinary storage.

    - Strips any directory path, keeping only the base name.
    - Normalizes Unicode (e.g. mathematical italic letters) to ASCII.
    - Replaces unsafe characters with underscores.
    - Guarantees a non-empty name with an extension.
    """
    if not filename:
        return "thumbnail.jpg"

    # Keep only the base filename (handle both / and \ separators)
    base_name = filename.replace("\\", "/").split("/")[-1]

    # Normalize unicode and drop characters that have no ASCII equivalent
    safe_name = (
        unicodedata.normalize("NFKD", base_name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    # Replace anything that is not a word char, dot, or hyphen
    safe_name = re.sub(r"[^\w\.\-]", "_", safe_name)

    # Collapse repeated underscores and strip leading/trailing dots/underscores
    safe_name = re.sub(r"_+", "_", safe_name).strip("._")

    # Fallback if everything was stripped away
    if not safe_name:
        return "thumbnail.jpg"

    # Ensure there is an extension
    if "." not in safe_name:
        safe_name += ".jpg"

    return safe_name


class Stream(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        ENDED = "ended", "Ended"

    class BroadcastType(models.TextChoices):
        BROWSER = "browser", "Browser"
        OBS = "obs", "OBS / RTMP"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="streams",
    )

    title = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    category = models.CharField(
        max_length=100,
        blank=True,
    )

    thumbnail = models.ImageField(
        upload_to="streams/thumbnails/",
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    broadcast_type = models.CharField(
        max_length=20,
        choices=BroadcastType.choices,
        default=BroadcastType.BROWSER,
    )

    # LiveKit configuration
    room_key = models.CharField(
        max_length=32,
        default=generate_room_key,
        unique=True,
    )

    # OBS / RTMP credentials
    stream_key = models.CharField(
        max_length=100,
        blank=True,
        default=generate_stream_key,
    )

    ingress_id = models.CharField(
        max_length=255,
        blank=True,
    )

    ingress_url = models.CharField(
        max_length=500,
        blank=True,
    )

    ingress_username = models.CharField(
        max_length=255,
        blank=True,
    )

    ingress_password = models.CharField(
        max_length=255,
        blank=True,
    )

    # Referenced by views.create_obs_ingress / end_stream
    ingress_stream_key = models.CharField(
        max_length=255,
        blank=True,
    )

    # Stream statistics
    viewer_count = models.PositiveIntegerField(
        default=0,
    )

    peak_viewers = models.PositiveIntegerField(
        default=0,
    )

    total_views = models.PositiveIntegerField(
        default=0,
    )

    # Visibility
    is_public = models.BooleanField(
        default=True,
    )

    # Stream timestamps
    scheduled_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    started_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    ended_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="stream_status_created_idx",
            ),
            models.Index(
                fields=["creator", "created_at"],
                name="stream_creator_created_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            base_slug = slugify(self.title) or "stream"
            self.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"

        if not self.room_key:
            self.room_key = generate_room_key()

        if not self.stream_key:
            self.stream_key = generate_stream_key()

        # Sanitize the thumbnail filename before Cloudinary receives it.
        # Cloudinary rejects public_ids containing unsupported Unicode
        # characters (e.g. mathematical italic letters).
        if self.thumbnail and hasattr(self.thumbnail, "name"):
            safe_name = sanitize_filename(self.thumbnail.name)
            self.thumbnail.name = f"streams/thumbnails/{safe_name}"

        super().save(*args, **kwargs)

    @property
    def is_live(self):
        return self.status == self.Status.LIVE

    def __str__(self):
        return self.title


class StreamChatMessage(models.Model):

    stream = models.ForeignKey(
        Stream,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stream_chat_messages",
    )

    message = models.TextField(
        max_length=1000,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["stream", "created_at"],
                name="stream_chat_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.stream.title}"
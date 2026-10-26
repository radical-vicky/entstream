
from django.conf import settings
from django.db import models
from django.urls import reverse
from cloudinary.models import CloudinaryField
from cloudinary.utils import cloudinary_url


class Video(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_videos",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Store video files in Cloudinary, not on the local server.
    video_file = CloudinaryField(
        "video",
        resource_type="video",
        folder="streamsphere/videos",
    )

    is_premium = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration = models.CharField(max_length=20, blank=True)
    views = models.PositiveBigIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("videos:detail", kwargs={"pk": self.pk})

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def thumbnail_url(self):
        """Generate a thumbnail from the uploaded video."""
        if not self.video_file:
            return ""

        public_id = getattr(self.video_file, "public_id", None)

        if not public_id:
            return ""

        url, _ = cloudinary_url(
            public_id,
            resource_type="video",
            format="jpg",
            secure=True,
            transformation=[
                {"width": 640, "height": 360, "crop": "fill"},
                {"start_offset": "2"},
            ],
        )

        return url



class VideoLike(models.Model):
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="video_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["video", "user"],
                name="unique_video_like_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} likes {self.video}"


class VideoComment(models.Model):
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="video_comments",
    )
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user} on {self.video}"



from django.conf import settings
from django.db import models


class VideoPurchase(models.Model):
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="video_purchases",
    )
    video = models.ForeignKey(
        "videos.Video",
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    payment_reference = models.CharField(
        max_length=80,
        unique=True,
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-purchased_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "video"],
                name="unique_video_purchase_per_buyer",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paid__gte=0),
                name="video_purchase_amount_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.buyer} purchased {self.video}"

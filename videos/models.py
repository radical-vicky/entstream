
from django.conf import settings
from django.db import models
from django.urls import reverse


class Video(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Source(models.TextChoices):
        CLOUDINARY = "cloudinary", "Cloudinary"
        BUNNY = "bunny", "Bunny Stream"
        YOUTUBE = "youtube", "YouTube"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_videos",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Video source
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.CLOUDINARY,
        db_index=True,
    )

    # Existing Cloudinary URL
    video_file = models.URLField(
        max_length=500,
        blank=True,
        help_text="Cloudinary video URL",
    )

    # Bunny Stream information
    bunny_video_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    bunny_library_id = models.CharField(
        max_length=100,
        blank=True,
    )

    # YouTube information
    youtube_video_id = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
    )

    # Optional thumbnail override
    custom_thumbnail = models.URLField(
        max_length=500,
        blank=True,
    )

    is_premium = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

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
        return reverse(
            "videos:detail",
            kwargs={"pk": self.pk},
        )

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def thumbnail_url(self):

        if self.custom_thumbnail:
            return self.custom_thumbnail

        if self.source == self.Source.BUNNY:
            if self.bunny_video_id and self.bunny_library_id:
                return (
                    f"https://vz-{self.bunny_library_id}.b-cdn.net/"
                    f"{self.bunny_video_id}/thumbnail.jpg"
                )

        if self.source == self.Source.YOUTUBE:
            if self.youtube_video_id:
                return (
                    "https://i.ytimg.com/vi/"
                    f"{self.youtube_video_id}/hqdefault.jpg"
                )

        if self.source == self.Source.CLOUDINARY:
            if not self.video_file:
                return ""

            if "/video/upload/" in self.video_file:
                return self.video_file.replace(
                    "/video/upload/",
                    "/video/upload/w_640,h_360,c_fill,so_2/",
                ).replace(".mp4", ".jpg").replace(
                    ".webm", ".jpg"
                ).replace(".mov", ".jpg")

        return ""

    @property
    def playback_url(self):

        if self.source == self.Source.BUNNY:
            if self.bunny_video_id and self.bunny_library_id:
                return (
                    f"https://iframe.mediadelivery.net/embed/"
                    f"{self.bunny_library_id}/{self.bunny_video_id}"
                )

        if self.source == self.Source.YOUTUBE:
            if self.youtube_video_id:
                return (
                    "https://www.youtube-nocookie.com/embed/"
                    f"{self.youtube_video_id}"
                    "?rel=0&playsinline=1&enablejsapi=1"
                )

        if self.source == self.Source.CLOUDINARY:
            return self.video_file

        return ""


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

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="KES",
    )

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

from django.conf import settings
from django.db import models
from django.urls import reverse

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

    # Cloudinary URL instead of a file upload
    video_file = models.URLField(max_length=500, help_text="Cloudinary Video URL")

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
        if not self.video_file:
            return ""
        if self.video_file.endswith(('.mp4', '.webm', '.mov', '.avi')):
            return self.video_file.rsplit('.', 1)[0] + '.jpg'
        return self.video_file


class VideoLike(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="video_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["video", "user"], name="unique_video_like_per_user"),
        ]

    def __str__(self):
        return f"{self.user} likes {self.video}"


class VideoComment(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="video_comments")
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user} on {self.video}"


# The missing model causing the build error
class VideoPurchase(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="purchases")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="video_purchases")
    purchased_at = models.DateTimeField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-purchased_at"]
        constraints = [
            models.UniqueConstraint(fields=["video", "user"], name="unique_video_purchase_per_user"),
        ]

    def __str__(self):
        return f"{self.user} purchased {self.video}"

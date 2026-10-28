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

    # CHANGED: Using URLField instead of CloudinaryField to accept the direct URL
    video_file = models.URLField(
        max_length=500, 
        help_text="Cloudinary video URL"
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
        """Generate a thumbnail from the Cloudinary URL."""
        if not self.video_file:
            return ""

        # Cloudinary URL format: https://res.cloudinary.com/cloud_name/video/upload/v12345/folder/filename.mp4
        # We need to replace '/video/upload/' with '/video/upload/w_640,h_360,c_fill,so_2/'
        if "/video/upload/" in self.video_file:
            return self.video_file.replace(
                "/video/upload/", 
                "/video/upload/w_640,h_360,c_fill,so_2/"
            ).replace(".mp4", ".jpg").replace(".webm", ".jpg").replace(".mov", ".jpg")
            
        return ""

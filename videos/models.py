from django.conf import settings
from django.db import models
from django.urls import reverse


class Video(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="videos",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # CHANGED: Now a URLField to store the Cloudinary URL securely
    video_file = models.URLField(
        max_length=500, 
        help_text="Cloudinary video URL"
    )
    
    # Optional: Add a thumbnail URL if you plan to generate thumbnails via Cloudinary
    thumbnail_url = models.URLField(
        max_length=500, 
        blank=True, 
        help_text="Cloudinary thumbnail URL"
    )
    
    duration = models.CharField(
        max_length=20, 
        blank=True, 
        help_text="e.g., 08:35"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
    )
    
    # Premium / Monetization fields
    is_premium = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Price in KES or your default currency"
    )
    
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["creator", "status"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("videos:detail", kwargs={"pk": self.pk})


from django.conf import settings
from django.db import models


class CatalogTitle(models.Model):
    MOVIE = "movie"
    TV = "tv"

    MEDIA_TYPES = [
        (MOVIE, "Movie"),
        (TV, "TV Series"),
    ]

    title = models.CharField(max_length=255)
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPES,
    )
    tmdb_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    overview = models.TextField(blank=True)
    poster_path = models.URLField(blank=True)
    backdrop_path = models.URLField(blank=True)
    release_date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["media_type", "tmdb_id"],
                name="unique_catalog_tmdb_title",
            )
        ]

    def __str__(self):
        return self.title


class Season(models.Model):
    series = models.ForeignKey(
        CatalogTitle,
        on_delete=models.CASCADE,
        related_name="seasons",
        limit_choices_to={"media_type": "tv"},
    )
    season_number = models.PositiveIntegerField()
    name = models.CharField(max_length=255, blank=True)
    overview = models.TextField(blank=True)

    class Meta:
        ordering = ["season_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["series", "season_number"],
                name="unique_series_season",
            )
        ]

    def __str__(self):
        return f"{self.series.title} - Season {self.season_number}"


class VideoAsset(models.Model):
    BUNNY = "bunny"
    EXTERNAL = "external"

    PROVIDERS = [
        (BUNNY, "Bunny Stream"),
        (EXTERNAL, "Licensed External Provider"),
    ]

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    PENDING = "pending"

    STATUSES = [
        (PENDING, "Pending upload"),
        (PROCESSING, "Processing"),
        (READY, "Ready to stream"),
        (FAILED, "Failed"),
    ]

    provider = models.CharField(
        max_length=20,
        choices=PROVIDERS,
        default=BUNNY,
    )
    provider_video_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    provider_library_id = models.CharField(
        max_length=100,
        blank=True,
    )
    external_embed_url = models.URLField(
        blank=True,
        help_text="Only use an authorized provider playback URL.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default=PENDING,
    )
    duration_seconds = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.provider_video_id or f"Video asset #{self.pk}"


class MovieStream(models.Model):
    title = models.OneToOneField(
        CatalogTitle,
        on_delete=models.CASCADE,
        related_name="movie_stream",
        limit_choices_to={"media_type": "movie"},
    )
    video = models.ForeignKey(
        VideoAsset,
        on_delete=models.PROTECT,
        related_name="movie_streams",
    )

    def __str__(self):
        return f"{self.title.title} stream"


class Episode(models.Model):
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name="episodes",
    )
    episode_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    overview = models.TextField(blank=True)
    air_date = models.DateField(null=True, blank=True)
    video = models.ForeignKey(
        VideoAsset,
        on_delete=models.PROTECT,
        related_name="episodes",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["season__season_number", "episode_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["season", "episode_number"],
                name="unique_season_episode",
            )
        ]

    def __str__(self):
        return (
            f"{self.season.series.title} "
            f"S{self.season.season_number:02d}E{self.episode_number:02d}"
        )


class ExternalProvider(models.Model):
    name = models.CharField(max_length=150)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ExternalTitleStream(models.Model):
    title = models.ForeignKey(
        CatalogTitle,
        on_delete=models.CASCADE,
        related_name="external_streams",
    )
    provider = models.ForeignKey(
        ExternalProvider,
        on_delete=models.PROTECT,
        related_name="title_streams",
    )
    playback_url = models.URLField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title.title} - {self.provider.name}"


class WatchProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="catalog_watch_progress",
    )
    video = models.ForeignKey(
        VideoAsset,
        on_delete=models.CASCADE,
        related_name="watch_progress",
    )
    position_seconds = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "video"],
                name="unique_user_video_progress",
            )
        ]


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="catalog_watchlist",
    )
    title = models.ForeignKey(
        CatalogTitle,
        on_delete=models.CASCADE,
        related_name="watchlist_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "title"],
                name="unique_user_catalog_watchlist",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.title.title}"

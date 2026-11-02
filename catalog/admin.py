
from django.contrib import admin

from .models import (
    CatalogTitle,
    Season,
    VideoAsset,
    MovieStream,
    Episode,
    ExternalProvider,
    ExternalTitleStream,
    WatchProgress,
    Watchlist,
)


class SeasonInline(admin.TabularInline):
    model = Season
    extra = 0
    fields = ("season_number", "name", "overview")
    show_change_link = True


class MovieStreamInline(admin.StackedInline):
    model = MovieStream
    extra = 0
    autocomplete_fields = ("video",)


class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    fields = (
        "episode_number",
        "title",
        "video",
        "is_published",
    )
    show_change_link = True
    autocomplete_fields = ("video",)


@admin.register(CatalogTitle)
class CatalogTitleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "media_type",
        "tmdb_id",
        "is_published",
        "is_premium",
        "created_at",
    )

    list_filter = (
        "media_type",
        "is_published",
        "is_premium",
    )

    search_fields = ("title", "tmdb_id")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25

    inlines = [
        MovieStreamInline,
        SeasonInline,
    ]


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = (
        "series",
        "season_number",
        "name",
    )

    list_filter = ("season_number",)
    search_fields = ("series__title", "name")
    autocomplete_fields = ("series",)
    inlines = [EpisodeInline]


@admin.register(VideoAsset)
class VideoAssetAdmin(admin.ModelAdmin):
    list_display = (
        "provider_video_id",
        "provider",
        "provider_library_id",
        "status",
        "duration_seconds",
        "is_active",
        "created_at",
    )

    list_filter = (
        "provider",
        "status",
        "is_active",
    )

    search_fields = (
        "provider_video_id",
        "provider_library_id",
        "external_embed_url",
    )

    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "season",
        "episode_number",
        "air_date",
        "is_published",
        "created_at",
    )

    list_filter = (
        "is_published",
        "air_date",
    )

    search_fields = (
        "title",
        "season__series__title",
    )

    autocomplete_fields = ("season", "video")
    readonly_fields = ("created_at",)


@admin.register(ExternalProvider)
class ExternalProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "website", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(ExternalTitleStream)
class ExternalTitleStreamAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "is_active")
    list_filter = ("provider", "is_active")
    search_fields = ("title__title", "provider__name")
    autocomplete_fields = ("title", "provider")


@admin.register(WatchProgress)
class WatchProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "video",
        "position_seconds",
        "completed",
        "updated_at",
    )

    list_filter = ("completed", "updated_at")
    search_fields = (
        "user__username",
        "video__provider_video_id",
    )

    readonly_fields = ("updated_at",)
    autocomplete_fields = ("user", "video")


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "created_at")
    search_fields = ("user__username", "title__title")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user", "title")

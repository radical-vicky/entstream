
from django.contrib import admin

from .models import LiveStream


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "creator",
        "status",
        "scheduled_at",
        "viewer_count",
        "total_views",
        "is_public",
    )
    list_filter = ("status", "is_public", "category", "created_at")
    search_fields = ("title", "creator__username", "description", "category")
    readonly_fields = (
        "stream_key",
        "started_at",
        "ended_at",
        "viewer_count",
        "peak_viewers",
        "total_views",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "scheduled_at"
    ordering = ("-created_at",)

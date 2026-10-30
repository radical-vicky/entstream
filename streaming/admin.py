
from django.contrib import admin

from .models import Stream, StreamChatMessage


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "creator",
        "status",
        "broadcast_type",
        "viewer_count",
        "created_at",
    )

    list_filter = (
        "status",
        "broadcast_type",
        "is_public",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "creator__username",
        "room_key",
    )

    readonly_fields = (
        "id",
        "room_key",
        "stream_key",
        "ingress_id",
        "ingress_url",
        "ingress_username",
        "ingress_password",
        "viewer_count",
        "peak_viewers",
        "total_views",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Stream information",
            {
                "fields": (
                    "creator",
                    "title",
                    "slug",
                    "description",
                    "category",
                    "thumbnail",
                    "status",
                    "broadcast_type",
                    "is_public",
                )
            },
        ),
        (
            "LiveKit and OBS configuration",
            {
                "fields": (
                    "room_key",
                    "stream_key",
                    "ingress_id",
                    "ingress_url",
                    "ingress_username",
                    "ingress_password",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "viewer_count",
                    "peak_viewers",
                    "total_views",
                )
            },
        ),
        (
            "Schedule and timestamps",
            {
                "fields": (
                    "scheduled_at",
                    "started_at",
                    "ended_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(StreamChatMessage)
class StreamChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "stream",
        "user",
        "message",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "stream__title",
        "user__username",
        "message",
    )

    readonly_fields = (
        "created_at",
    )

from django.contrib import admin

from .models import ModerationAction, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_type",
        "target_id",
        "reason",
        "reporter",
        "status",
        "reviewer",
        "created_at",
    )
    list_filter = ("status", "target_type", "reason", "created_at")
    search_fields = (
        "reporter__username",
        "reporter__email",
        "resolution_note",
        "details",
    )
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
    list_select_related = ("reporter", "reviewer")


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action_type",
        "target_type",
        "target_id",
        "moderator",
        "report",
        "created_at",
    )
    list_filter = ("action_type", "target_type", "created_at")
    search_fields = (
        "moderator__username",
        "note",
    )
    readonly_fields = ("created_at",)
    list_select_related = ("moderator", "report")
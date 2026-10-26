from django.contrib import admin
from .models import Video, VideoLike, VideoComment


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "creator",
        "status",
        "is_premium",
        "views",
        "created_at",
    )
    list_filter = ("status", "is_premium", "created_at")
    search_fields = ("title", "description", "creator__username")
    list_select_related = ("creator",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(VideoLike)
class VideoLikeAdmin(admin.ModelAdmin):
    list_display = ("video", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("video__title", "user__username")
    list_select_related = ("video", "user")
    readonly_fields = ("created_at",)


@admin.register(VideoComment)
class VideoCommentAdmin(admin.ModelAdmin):
    list_display = ("video", "user", "short_text", "created_at")
    list_filter = ("created_at",)
    search_fields = ("text", "video__title", "user__username")
    list_select_related = ("video", "user")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Comment")
    def short_text(self, obj):
        return obj.text[:70] + ("…" if len(obj.text) > 70 else "")
    


from .models import VideoPurchase

@admin.register(VideoPurchase)
class VideoPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "buyer",
        "video",
        "amount_paid",
        "currency",
        "payment_reference",
        "purchased_at",
    )
    search_fields = (
        "buyer__username",
        "video__title",
        "payment_reference",
    )
    list_filter = ("currency", "purchased_at")
    readonly_fields = (
        "buyer",
        "video",
        "amount_paid",
        "currency",
        "payment_reference",
        "purchased_at",
    )

from .models import VideoPurchase


def can_user_watch_video(user, video):
    if not video.is_premium:
        return True

    if not user or not user.is_authenticated:
        return False

    if user.is_staff or user.pk == video.creator_id:
        return True

    return VideoPurchase.objects.filter(
        buyer=user,
        video=video,
    ).exists()
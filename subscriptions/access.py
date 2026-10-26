
from django.utils import timezone

from .models import UserSubscription


def user_has_active_subscription(user):
    if not user or not user.is_authenticated:
        return False

    return UserSubscription.objects.filter(
        user=user,
        status=UserSubscription.Status.ACTIVE,
        expires_at__gt=timezone.now(),
    ).exists()

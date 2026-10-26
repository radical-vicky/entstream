
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.models import Notification
from .models import Follow

User = get_user_model()


@login_required
@require_POST
def toggle_follow(request, username):
    creator = get_object_or_404(User, username=username)

    if creator.pk == request.user.pk:
        return redirect("accounts:profile")

    existing = Follow.objects.filter(
        follower=request.user,
        following=creator,
    )

    if existing.exists():
        existing.delete()
    else:
        Follow.objects.get_or_create(
            follower=request.user,
            following=creator,
        )
        Notification.objects.create(
            recipient=creator,
            actor=request.user,
            notification_type=Notification.Type.FOLLOW,
        )

    return redirect(request.POST.get("next") or "accounts:profile")

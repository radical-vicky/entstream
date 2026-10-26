from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.models import Notification
from .models import Follow


User = get_user_model()


@login_required
@require_POST
def toggle_follow(request, username):
    creator = get_object_or_404(User, username=username)

    if creator.pk == request.user.pk:
        messages.info(request, "You cannot follow your own account.")
        return redirect("accounts:profile")

    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=creator,
    )

    if created:
        Notification.objects.create(
            recipient=creator,
            actor=request.user,
            notification_type=Notification.Type.FOLLOW,
        )
        messages.success(request, f"You are now following {creator.username}.")
    else:
        follow.delete()
        messages.info(request, f"You unfollowed {creator.username}.")

    next_url = request.POST.get("next", "").strip()

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect("accounts:profile")

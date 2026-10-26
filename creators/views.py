
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.models import Profile, Notification
from videos.models import Video
from .models import Follow

User = get_user_model()


def creator_profile(request, username):
    creator = get_object_or_404(
        User.objects.select_related("profile"),
        username=username,
    )

    profile, _ = Profile.objects.get_or_create(user=creator)

    videos = (
        Video.objects
        .filter(creator=creator, status="published")
        .order_by("-created_at")
    )

    followers_count = Follow.objects.filter(following=creator).count()
    following_count = Follow.objects.filter(follower=creator).count()

    is_following = False

    if request.user.is_authenticated and request.user.pk != creator.pk:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=creator,
        ).exists()

    return render(
        request,
        "creators/creator_profile.html",
        {
            "creator": creator,
            "profile": profile,
            "videos": videos,
            "followers_count": followers_count,
            "following_count": following_count,
            "is_following": is_following,
            "video_count": videos.count(),
        },
    )


@login_required
@require_POST
def toggle_follow(request, username):
    creator = get_object_or_404(User, username=username)

    if creator.pk == request.user.pk:
        messages.error(request, "You cannot follow your own account.")
        return redirect("creators:profile", username=creator.username)

    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=creator,
    )

    if created:
        # Avoid sending a notification to the same user.
        Notification.objects.create(
            recipient=creator,
            actor=request.user,
            notification_type="follow",
        )
        messages.success(
            request,
            f"You are now following {creator.username}.",
        )
    else:
        follow.delete()
        messages.info(
            request,
            f"You unfollowed {creator.username}.",
        )

    next_url = request.POST.get("next", "").strip()

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect("creators:profile", username=creator.username)

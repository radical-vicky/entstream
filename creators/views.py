from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
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

    active_tab = request.GET.get("tab", "videos")

    # Fetch the video queryset
    videos = (
        Video.objects
        .filter(creator=creator, status="published")
        .order_by("-created_at")
    )

    # Follow relationships
    followers_qs = Follow.objects.filter(following=creator).select_related("follower", "follower__profile")
    following_qs = Follow.objects.filter(follower=creator).select_related("following", "following__profile")

    followers_count = followers_qs.count()
    following_count = following_qs.count()

    is_following = False
    if request.user.is_authenticated and request.user.pk != creator.pk:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=creator,
        ).exists()

    # Calculate total views
    total_views = sum(v.views or 0 for v in videos)

    context = {
        "creator": creator,
        "profile": profile,
        "is_following": is_following,
        "active_tab": active_tab,
        "followers_count": followers_count,
        "following_count": following_count,
        "video_count": videos.count(),
        "total_views": total_views,
        
        # Only pass the data needed for the active tab
        "videos": videos if active_tab == "videos" else [],
        "followers": [f.follower for f in followers_qs] if active_tab == "followers" else [],
        "following": [f.following for f in following_qs] if active_tab == "following" else [],
    }

    return render(request, "creators/creator_profile.html", context)


@login_required
@require_POST
def toggle_follow(request, username):
    creator = get_object_or_404(User, username=username)

    if creator.pk == request.user.pk:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "You cannot follow your own account."}, status=400)
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
        following = True
    else:
        follow.delete()
        following = False

    # Return JSON for AJAX requests
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "following": following,
            "count": Follow.objects.filter(following=creator).count(),
        })

    # Fallback redirect for non-JS submissions
    if created:
        messages.success(request, f"You are now following {creator.username}.")
    else:
        messages.info(request, f"You unfollowed {creator.username}.")

    next_url = request.POST.get("next", "").strip()

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect("creators:profile", username=creator.username)
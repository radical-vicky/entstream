from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Profile, Notification


@login_required
def my_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        profile.bio = request.POST.get("bio", "").strip()
        profile.location = request.POST.get("location", "").strip()
        profile.website = request.POST.get("website", "").strip()

        avatar_file = request.FILES.get("avatar_image")

        if avatar_file:
            allowed_types = {
                "image/jpeg",
                "image/png",
                "image/webp",
            }

            if avatar_file.content_type not in allowed_types:
                messages.error(
                    request,
                    "Upload a JPG, PNG, or WebP image."
                )
                return redirect("accounts:profile")

            if avatar_file.size > 5 * 1024 * 1024:
                messages.error(
                    request,
                    "Your profile image must be 5 MB or smaller."
                )
                return redirect("accounts:profile")

            profile.avatar_image = avatar_file

        profile.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("accounts:profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
        },
    )


@login_required
def notification_list(request):
    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("actor", "video", "comment")
        .order_by("-created_at")
    )

    unread_count = notifications.filter(is_read=False).count()

    paginator = Paginator(notifications, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications": page_obj,
            "page_obj": page_obj,
            "unread_count": unread_count,
        },
    )


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )

    notification.is_read = True
    notification.save(update_fields=["is_read"])

    next_url = request.POST.get("next", "").strip()

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    if notification.video_id:
        return redirect("videos:detail", pk=notification.video_id)

    return redirect("accounts:notifications")


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)

    messages.success(request, "All notifications marked as read.")
    return redirect("accounts:notifications")